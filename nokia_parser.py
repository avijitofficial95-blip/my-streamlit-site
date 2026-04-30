import pandas as pd
import os

def extract_lines_from_file(uploaded_file):
    if uploaded_file.name.endswith(".txt"):
        return uploaded_file.getvalue().decode("utf-8", errors="replace").splitlines()
    elif uploaded_file.name.endswith((".xlsx", ".xls")):
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
         
    result = list(dict.fromkeys(down_ports))
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

def extract_dhcp_string(raw_block, keyword="dhcp"):
    lines = raw_block.split('\n')
    in_dhcp = False
    dhcp_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped == keyword:
            in_dhcp = True
            dhcp_lines.append(stripped)
        elif in_dhcp:
            dhcp_lines.append(stripped)
            if stripped == "exit":
                break
                
    return "\n".join(dhcp_lines) if dhcp_lines else ""

def extract_interface_details(text_lines):
    interfaces = []
    current_context = "Base"
    current_interface = None
    current_address = None
    current_sap = None
    intf_desc = ""
    sap_desc = ""
    in_sap = False
    has_dhcp = False
    
    current_block = []
    capture_block = False
    
    for line in text_lines:
        stripped = line.strip()
        
        if stripped.startswith("vprn "):
            current_context = stripped.split(" ")[1]
        elif stripped.startswith("router "):
            current_context = "Base"
            
        if stripped.startswith("interface "):
            # Save previous if dangling
            if capture_block and current_interface:
                interfaces.append({
                    "context": current_context, "name": current_interface, "address": current_address, 
                    "sap": current_sap, "intf_desc": intf_desc, "sap_desc": sap_desc, 
                    "has_dhcp": has_dhcp, "raw_block": "\n".join(current_block)
                })
            parts = stripped.split(' ', 1)
            if len(parts) > 1:
                current_interface = parts[1].replace('"', '').replace(' create', '')
                current_address = None
                current_sap = None
                intf_desc = ""
                sap_desc = ""
                in_sap = False
                has_dhcp = False
                current_block = [line]
                capture_block = True
                
        elif current_interface:
            if capture_block:
                current_block.append(line)
                
            if stripped.startswith("address "):
                current_address = stripped.split(' ', 1)[1]
            elif stripped in ("dhcp", "dhcp6-relay"):
                has_dhcp = True
            elif stripped.startswith("sap "):
                if not current_sap:
                    current_sap = stripped.split()[1] 
                in_sap = True
            elif stripped.startswith("description "):
                desc = stripped.split(' ', 1)[1]
                if in_sap:
                    if not sap_desc: sap_desc = desc
                elif not intf_desc:
                    intf_desc = desc
            elif stripped == "exit" and in_sap:
                in_sap = False
            elif stripped == "exit all" or stripped.startswith(("echo", "#", "port ", "vpls ", "vll ", "router ", "vprn ", "service ", "spoke-sdp ", "system ")):
                if capture_block:
                    interfaces.append({
                        "context": current_context, "name": current_interface, "address": current_address, 
                        "sap": current_sap, "intf_desc": intf_desc, "sap_desc": sap_desc, 
                        "has_dhcp": has_dhcp, "raw_block": "\n".join(current_block)
                    })
                    capture_block = False
                    current_interface = None
                    
    if current_interface and capture_block:
        interfaces.append({
            "context": current_context, "name": current_interface, "address": current_address, 
            "sap": current_sap, "intf_desc": intf_desc, "sap_desc": sap_desc, 
            "has_dhcp": has_dhcp, "raw_block": "\n".join(current_block)
        })
        
    return interfaces

def get_router_model(target_router):
    last_four = target_router[-4:]
    if last_four in ["IXRB", "IXRC", "IXR2", "IXR6"]:
        return "IXR"
    elif last_four in ["SR01", "SRA4", "SAR8", "SRA8", "SR12"]:
        return "SR"
    return "UNKNOWN"

def load_vrf_mapping():
    mapping = {}
    path = os.path.join("vrf mapping", "nokia_to_nokia_vprn_mapping.txt")
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                if ":" in line:
                    k, v = line.strip().split(":", 1)
                    mapping[k] = v
    return mapping

def read_template(template_name):
    path = os.path.join("templates", template_name)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return f"# TEMPLATE {template_name} MISSING"

def apply_replacements(text, mapping_dict):
    for k, v in mapping_dict.items():
        if v is not None:
            text = text.replace(k, str(v))
    return text

def parse_target_sapports(router_log_lines):
    # To check if vlan is already used. Return list of target_port:target_vlan.
    saps = []
    for line in router_log_lines:
        line = line.strip()
        if line.startswith("sap ") and "create" in line:
             sap_part = line.split()[1]
             saps.append(sap_part)
    return saps

def generate_migration_configs(excel_file, router_log_lines):
    df_input = pd.read_excel(excel_file)
    df_input = df_input.fillna("")
    
    interfaces = extract_interface_details(router_log_lines)
    admin_down_ports_list = [p["Port"] for p in get_admin_down_ports(router_log_lines)]
    used_saps = parse_target_sapports(router_log_lines)
    vrf_map = load_vrf_mapping()
    
    warnings = []
    visited_ports = set()
    site_data = {}
    
    for index, row in df_input.iterrows():
        site_id = str(row.get("site_id", "")).strip()
        if not site_id: continue
            
        if site_id not in site_data:
            site_data[site_id] = {
                "auto_deletions": [],
                "auto_creations": [],
                "manual": {
                    "vlan_dels": [],
                    "ports": [],
                    "vlan_cres": [],
                    "vlan_rols": [],
                    "vlan_prols": []
                }
            }
            
        parent_router = str(row.get("parent_router", "")).strip()
        parent_port = str(row.get("parent_port", "")).strip()
        
        try:
            r_vlan_src = row.get("src_vlan", "")
            src_vlan = str(int(float(r_vlan_src))) if str(r_vlan_src).strip() else ""
        except ValueError:
            src_vlan = str(r_vlan_src).strip()
            
        try:
            r_vlan_tgt = row.get("target_vlan", "")
            target_vlan = str(int(float(r_vlan_tgt))) if str(r_vlan_tgt).strip() else ""
        except ValueError:
            target_vlan = str(r_vlan_tgt).strip()
            
        target_router = str(row.get("target_router", "")).strip()
        target_port = str(row.get("target_port", "")).strip()
        bandwidth = str(row.get("bandwidth", "")).strip()
        
        if not parent_router or not target_router or not parent_port:
            continue
            
        parent_sap = f"{parent_port}:{src_vlan}"
        target_sap = f"{target_port}:{target_vlan}"
        
        if target_sap in used_saps:
            warnings.append(f"Target SAP '{target_sap}' already exists in target_router config. VLAN is already used.")
            site_data[site_id]["manual"]["vlan_dels"].extend([
                 f"# ERROR: Target SAP '{target_sap}' already exists. VLAN used #"
            ])
            continue
            
        is_admin_down = target_port in admin_down_ports_list
        if is_admin_down and not "lag" in target_port.lower():
            warnings.append(f"Target interface '{target_port}' on {target_router} is currently Admin Down")
            
        matched_intf = None
        for intf in interfaces:
            isap = intf["sap"].strip() if intf["sap"] else ""
            if isap == parent_sap or isap.startswith(f"{parent_sap} ") or isap.startswith(f"{parent_sap}:"):
                matched_intf = intf
                break
                
        if matched_intf:
            intf_name = matched_intf["name"]
            address = matched_intf.get("address") or ""
            actual_sap = matched_intf["sap"]
            vprn = matched_intf["context"]
            i_desc = matched_intf.get("intf_desc", '"Extracted_Interface_Desc"')
            s_desc = matched_intf.get("sap_desc", '"Extracted_SAP_Desc"')
            raw_block = matched_intf.get("raw_block", "")
            has_dhcp = matched_intf.get("has_dhcp", False)
            
            target_vprn = vrf_map.get(vprn, vprn)
            
            # --- Deletion ---
            del_template = read_template("nokia_delete.txt")
            del_block = apply_replacements(del_template, {
                '"extracted_vrf"': vprn,
                '"extracted_interface_line"': intf_name,
                "parent_port:src_vlan": actual_sap
            })
            
            # --- Port injection if Admin Down ---
            port_injection = ""
            port_key = f"{target_router}:{target_port}"
            if is_admin_down and not "lag" in target_port.lower() and port_key not in visited_ports:
                visited_ports.add(port_key)
                if bandwidth.lower() in ("1g", "1000"):
                    p_temp = ""
                    last_four = target_router[-4:]
                    if last_four in ["IXRB", "IXRC"]: p_temp = "port_configuration_ixrb.c.txt"
                    elif last_four == "IXR2": p_temp = "port_configuration_ixr2.txt"
                    elif last_four in ["SR01", "SRA4", "SAR8", "SRA8", "SR12"]: p_temp = "port_configuration_sr.txt"
                    else: p_temp = "port_configuration_sr.txt"
                    ptxt = read_template(p_temp)
                    port_injection = apply_replacements(ptxt, {"target_port": target_port})
                else:
                    port_injection = f"configure port {target_port}\nshutdown\nethernet\n speed {bandwidth}\nexit\nno shutdown\nexit\n"
                 
            # --- Creation ---
            model_type = get_router_model(target_router)
            is_ipv6 = ":" in address
            
            template_name = ""
            if model_type == "IXR":
                if is_ipv6 and not has_dhcp: template_name = "nokia_ixr_ipv6_creation.txt"
                elif is_ipv6 and has_dhcp: template_name = "nokia_ixr_ipv6_dhcpv6_creation.txt"
                elif not is_ipv6 and not has_dhcp: template_name = "nokia_ixr_ipv4_creation.txt"
                elif not is_ipv6 and has_dhcp: template_name = "nokia_ixr_ipv4_dhcp_creation.txt"
            else:
                if is_ipv6 and not has_dhcp: template_name = "nokia_sr_ipv6_creation.txt"
                elif is_ipv6 and has_dhcp: template_name = "nokia_sr_ipv6_dhcpv6_creation.txt"
                elif not is_ipv6 and not has_dhcp: template_name = "nokia_sr_ipv4_creation.txt"
                elif not is_ipv6 and has_dhcp: template_name = "nokia_sr_ipv4_dhcp_creation.txt"
                    
            add_template = read_template(template_name)
            extracted_dhcp = extract_dhcp_string(raw_block, "dhcp")
            extracted_dhcp6 = extract_dhcp_string(raw_block, "dhcp6-relay")
            
            cre_block_only = apply_replacements(add_template, {
                '"extracted_vrf"': target_vprn,
                'extracted_vrf': target_vprn,
                'target_port:target_vlan': target_sap,
                '"extracted_desc"': i_desc if i_desc else '""',
                'extracted_desc': i_desc.strip('"') if i_desc else '""',
                'address_ipv4': address,
                'address_ipv6': address,
                'dhcp_block': extracted_dhcp,
                'dhcpv6_block': extracted_dhcp6
            })
                
            rol_target = apply_replacements(del_template, {
                '"extracted_vrf"': target_vprn,
                '"extracted_interface_line"': f"GE-{target_sap}",
                "parent_port:src_vlan": target_sap
            })
            
            # --- Automation Lists ---
            del_lines = [l.strip() for l in del_block.strip().split("\n") if l.strip()]
            rol_lines = [l.strip() for l in rol_target.strip().split("\n") if l.strip()]
            
            for l in del_lines:
                site_data[site_id].setdefault("auto_left", []).append([parent_router, parent_sap, l])
            for l in rol_lines:
                site_data[site_id].setdefault("auto_right", []).append([target_router, l])
                
            cre_lines = []
            if port_injection: cre_lines.extend([l.strip() for l in port_injection.strip().split("\n") if l.strip()])
            cre_lines.extend([l.strip() for l in cre_block_only.strip().split("\n") if l.strip()])
            
            p_rol_lines = [f"configure service vprn {vprn}"] + [l.strip() for l in raw_block.strip().split("\n") if l.strip()]
            if p_rol_lines[-1] != "exit all":
                 p_rol_lines.append("exit all")
                 
            for l in cre_lines:
                site_data[site_id].setdefault("auto_left", []).append([target_router, target_sap, l])
            for l in p_rol_lines:
                site_data[site_id].setdefault("auto_right", []).append([parent_router, l])

            # --- Manual Lists ---
            if port_injection: site_data[site_id]["manual"]["ports"].extend([l.strip() for l in port_injection.strip().split("\n") if l.strip()])
            
            site_data[site_id]["manual"]["vlan_dels"].append(f"# vlan {src_vlan} deletion from parent_router {parent_router} #")
            site_data[site_id]["manual"]["vlan_dels"].extend(del_lines)
            
            site_data[site_id]["manual"]["vlan_cres"].append(f"# Vlan {target_vlan} creation in target_router {target_router} #")
            site_data[site_id]["manual"]["vlan_cres"].extend([l.strip() for l in cre_block_only.strip().split("\n") if l.strip()])
            
            site_data[site_id]["manual"]["vlan_rols"].append(f"# Vlan {target_vlan} deletion from target_router {target_router} #")
            site_data[site_id]["manual"]["vlan_rols"].extend(rol_lines)
            
            site_data[site_id]["manual"]["vlan_prols"].append(f"# vlan {src_vlan} creation in parent_router {parent_router} as per existing config backup #")
            site_data[site_id]["manual"]["vlan_prols"].extend(p_rol_lines)

        else:
            extracted_saps = [i['sap'] for i in interfaces if i['sap']]
            sampled = ", ".join(extracted_saps[:15]) if extracted_saps else "None found!"
            err_msg = f"Parent SAP '{parent_sap}' not found! (Found internally: {sampled}...)"
            warnings.append(err_msg)
            site_data[site_id]["manual"]["vlan_dels"].append(f"# ERROR: {err_msg}")

    # Compile Structured End Arrays
    auto_mop_rows = []
    manual_cols = []
    left_all = []
    right_all = []
    
    for sid, data in site_data.items():
        left_all.extend(data.get("auto_left", []))
        right_all.extend(data.get("auto_right", []))
        
        # Compile Manual
        col = []
        col.append(sid)
        col.append("")
        for txt in data["manual"]["vlan_dels"]: col.append(txt)
        col.append("")
        for txt in data["manual"]["ports"]: col.append(txt)
        for txt in data["manual"]["vlan_cres"]: col.append(txt)
        col.append("")
        col.append("Rollback")
        col.append("")
        for txt in data["manual"]["vlan_rols"]: col.append(txt)
        col.append("")
        for txt in data["manual"]["vlan_prols"]: col.append(txt)
        
        manual_cols.append(col)

    # Pad Auto MOP completely abstract from sites so it generates globally continuously
    for i in range(max(len(left_all), len(right_all))):
        row = []
        if i < len(left_all):
            row.extend(left_all[i])
        else:
            row.extend(["", "", ""])
            
        if i < len(right_all):
            row.extend(right_all[i])
        else:
            row.extend(["", ""])
            
        auto_mop_rows.append(row)
        
    # Pad manual list columns dynamically to avoid pandas matrix errors
    if manual_cols:
        max_rows = max([len(c) for c in manual_cols])
        for c in manual_cols:
            c.extend([""] * (max_rows - len(c)))
            
    df_auto = pd.DataFrame(auto_mop_rows, columns=["Hostname", "Interface", "Creation MOP", "Hostname.1", "Rollback MOP"])
    df_manual = pd.DataFrame(manual_cols).T
    if not df_manual.empty:
        df_manual.columns = ["site_id"] * len(df_manual.columns)
    else:
        df_manual = pd.DataFrame(columns=["site_id"])

    return df_auto, df_manual, warnings
