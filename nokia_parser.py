import pandas as pd

def extract_lines_from_file(uploaded_file):
    if uploaded_file.name.endswith(".txt"):
        return uploaded_file.getvalue().decode("utf-8", errors="ignore").splitlines()
    elif uploaded_file.name.endswith(".xlsx") or uploaded_file.name.endswith(".xls"):
        df = pd.read_excel(uploaded_file, header=None)
        return df[0].dropna().astype(str).tolist()
    return []

def get_admin_down_ports(text_lines):
    down_ports = []
    current_port = None
    is_down = False
    
    for line in text_lines:
        stripped = line.strip()
        if stripped.startswith("port "):
            if current_port and is_down:
                down_ports.append(current_port)
            current_port = stripped.split(" ", 1)[1].strip()
            is_down = False
        elif current_port:
            if stripped == "shutdown":
                is_down = True
            elif stripped == "no shutdown":
                is_down = False
            elif stripped.startswith("echo ") or stripped.startswith("router ") or stripped.startswith("#") or stripped.startswith("interface ") or stripped.startswith("vprn "):
                if is_down:
                    down_ports.append(current_port)
                current_port = None
                
    if current_port and is_down:
         down_ports.append(current_port)
         
    result = []
    for port in down_ports:
        if port not in result:
            result.append(port)
            
    return [{"Port": p, "Status": "Admin Down"} for p in result]

def get_vlan_ip_mapping(text_lines):
    vlan_mapping = []
    current_interface = None
    
    for line in text_lines:
        stripped = line.strip()
        
        if stripped.startswith("interface "):
            parts = stripped.split(' ', 1)
            if len(parts) > 1:
                current_interface = parts[1].replace('"', '').replace(' create', '')
                
        elif current_interface and stripped.startswith("address "):
            address_part = stripped.split(' ', 1)[1]
            ip_subnet = address_part.split('/')
            ip = ip_subnet[0]
            subnet = ip_subnet[1] if len(ip_subnet) > 1 else ""
            
            vlan_mapping.append({
                "Interface/VLAN": current_interface,
                "IP Address": ip,
                "Subnet Mask (CIDR)": "/" + subnet if subnet else ""
            })
            current_interface = None
            
        elif stripped.startswith("echo ") or stripped.startswith("port "):
            current_interface = None
            
    return vlan_mapping

def extract_interface_details(text_lines):
    """
    Parses L3 router interfaces to extract all details: Name, IP, Subnet, exact SAP, VPRN context, and Descriptions.
    """
    interfaces = []
    current_context = "Base"
    current_interface = None
    current_address = None
    current_sap = None
    intf_desc = ""
    sap_desc = ""
    in_sap = False
    in_dhcp = False
    
    for line in text_lines:
        stripped = line.strip()
        
        if stripped.startswith("vprn "):
            current_context = stripped.split(" ")[1]
        elif stripped.startswith("router "):
            current_context = "Base"
        elif stripped.startswith("interface "):
            parts = stripped.split(' ', 1)
            if len(parts) > 1:
                current_interface = parts[1].replace('"', '').replace(' create', '')
                current_address = None
                current_sap = None
                intf_desc = ""
                sap_desc = ""
                in_sap = False
                in_dhcp = False
                
        elif current_interface:
            if stripped.startswith("address "):
                address_part = stripped.split(' ', 1)[1]
                current_address = address_part 
            elif stripped.startswith("dhcp"):
                in_dhcp = True
            elif stripped.startswith("sap "):
                sap_part = stripped.split(' ')[1] 
                current_sap = sap_part 
                in_sap = True
            elif stripped.startswith("description "):
                desc = stripped.split(' ', 1)[1]
                if in_sap:
                    sap_desc = desc
                elif not in_dhcp and not intf_desc:
                    intf_desc = desc
            elif stripped == "exit":
                if in_sap:
                    in_sap = False
                elif in_dhcp:
                    in_dhcp = False
                elif current_address and current_sap:
                    interfaces.append({
                        "context": current_context,
                        "name": current_interface,
                        "address": current_address,
                        "sap": current_sap,
                        "intf_desc": intf_desc,
                        "sap_desc": sap_desc
                    })
                    current_interface = None
            elif stripped.startswith("echo") or stripped.startswith("#"):
                current_interface = None
                
    return interfaces

def generate_migration_configs(excel_file, router_log_lines):
    df = pd.read_excel(excel_file)
    df = df.fillna("")
    
    interfaces = extract_interface_details(router_log_lines)
    admin_down_ports_list = [p["Port"] for p in get_admin_down_ports(router_log_lines)]
    
    deletion_configs = []
    creation_configs = []
    warnings = []
    
    for index, row in df.iterrows():
        parent_router = str(row.get("Parent router", "")).strip()
        parent_intf = str(row.get("Parent interface", "")).strip()
        target_router = str(row.get("target router", "")).strip()
        target_intf = str(row.get("target interface", "")).strip()
        
        if not parent_router or not target_router or not parent_intf:
            continue
            
        if target_intf and target_intf in admin_down_ports_list:
            warning_msg = f"Target interface '{target_intf}' on {target_router} is currently Admin Down"
            if warning_msg not in warnings:
                warnings.append(warning_msg)
                
        vlans = []
        for col_name in df.columns:
            if str(col_name).lower().startswith("vlan"):
                v_value = row.get(col_name)
                if str(v_value).strip():
                    try:
                        v_val = int(float(str(v_value).strip()))
                        vlans.append(str(v_val))
                    except ValueError:
                        vlans.append(str(v_value).strip())
                        
        for vlan in vlans:
            expected_parent_sap = f"{parent_intf}:{vlan}"
            
            matched_intf = None
            for intf in interfaces:
                if intf["sap"] == expected_parent_sap or intf["sap"].startswith(f"{expected_parent_sap} "):
                    matched_intf = intf
                    break
            
            if matched_intf:
                intf_name = matched_intf["name"]
                address = matched_intf["address"]
                actual_sap = matched_intf["sap"]
                vprn = matched_intf["context"]
                i_desc = matched_intf.get("intf_desc", '"Extracted_Interface_Desc"')
                s_desc = matched_intf.get("sap_desc", '"Extracted_SAP_Desc"')
                ip_no_cidr = address.split("/")[0]
                
                service_cmd = f"configure service vprn {vprn}" if vprn != "Base" else "configure router"
                target_sap = f"{target_intf}:{vlan}"
                new_intf_name = f"GE-{target_sap}"
                
                # --- DELETION ---
                del_snip = f'# --- Deletion for VLAN {vlan} from {parent_router} ---\n'
                del_snip += f'{service_cmd}\n'
                del_snip += f'interface "{intf_name}" shutdown\n'
                del_snip += f'interface "{intf_name}" sap {actual_sap} shutdown\n'
                del_snip += f'interface "{intf_name}" no sap {actual_sap}\n'
                del_snip += f'no interface "{intf_name}"\n'
                del_snip += f'exit all\n\n'
                deletion_configs.append(del_snip)
                
                # --- CREATION ---
                add_snip = f'# --- Creation for VLAN {vlan} on {target_router} ---\n'
                add_snip += f'{service_cmd}\n'
                add_snip += f'interface "{new_intf_name}" create\n'
                if i_desc: add_snip += f'description {i_desc}\n'
                add_snip += f'address {address}\n'
                add_snip += f'dhcp\n'
                add_snip += f'description "DHCP-Relay-Agent"\n'
                add_snip += f'server 10.209.68.188\n'
                add_snip += f'trusted\n'
                add_snip += f'gi-address {ip_no_cidr} src-ip-addr\n'
                add_snip += f'no shutdown\n'
                add_snip += f'exit\n'
                add_snip += f'sap {target_sap} create\n'
                if s_desc: add_snip += f'description {s_desc}\n'
                add_snip += f'ingress\nqos 5001\nexit\n'
                add_snip += f'egress\nqos 5001\nexit\n'
                add_snip += f'exit\n'
                add_snip += f'exit all\n\n'
                creation_configs.append(add_snip)
            else:
                del_snip = f"# ERROR: SAP '{expected_parent_sap}' not found in the uploaded log!\n\n"
                deletion_configs.append(del_snip)
                
    return "".join(deletion_configs), "".join(creation_configs), warnings
