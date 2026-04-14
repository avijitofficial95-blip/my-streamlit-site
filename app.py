import streamlit as st
import pandas as pd
import io
import importlib
import nokia_parser
importlib.reload(nokia_parser)
from nokia_parser import extract_lines_from_file, get_admin_down_ports, get_vlan_ip_mapping, generate_migration_configs

st.set_page_config(page_title="Nokia Router Log Analyzer", page_icon="📶", layout="wide")

st.title("📶 Nokia Router Log Analyzer & MOP Generator")
st.markdown("Use this tool to parse your **`admin display configuration`** logs natively. Switch to the Migration tab if you want to upload a Service Migration Excel sheet to automatically generate deployment Configurations!")

tab1, tab2 = st.tabs(["📊 Standard Log Processing", "🔄 Service Migration MOP Generator"])

# ----------------- TAB 1 -----------------
with tab1:
    st.markdown("### Standard Output Extractor")
    uploaded_file = st.file_uploader("Upload Router Log File", type=["txt", "xlsx", "xls"], key="tab1_uploadd")

    if uploaded_file is not None:
        try:
            lines = extract_lines_from_file(uploaded_file)
            st.success(f"✅ Successfully loaded {len(lines)} lines of text from `{uploaded_file.name}`")
        except Exception as e:
            st.error(f"Error processing file: {e}")
            st.stop()

        st.markdown("### Output Requirements")
        col1, col2 = st.columns(2)
        with col1:
            req_mapping = st.checkbox("1. Extract VLAN-wise IP and Subnet Mapping", value=True)
        with col2:
            req_admin_down = st.checkbox("2. Extract List of Admin Down Ports", value=True)
            
        if st.button("Process Log", type="primary", use_container_width=True, key="tab1_btn"):
            st.markdown("---")
            mapping_data = []
            admin_data = []
            
            if req_mapping:
                st.subheader("🌐 VLAN-wise IP and Subnet Mapping")
                mapping_data = get_vlan_ip_mapping(lines)
                if mapping_data:
                    df_mapping = pd.DataFrame(mapping_data)
                    st.dataframe(df_mapping, use_container_width=True)
                else:
                    st.warning("No VLAN/IP mappings found in the uploaded file.")
                    
            if req_admin_down:
                st.write("") 
                st.subheader("🔌 Admin Down Ports")
                admin_data = get_admin_down_ports(lines)
                if admin_data:
                    df_admin = pd.DataFrame(admin_data)
                    st.dataframe(df_admin, use_container_width=True)
                else:
                    st.warning("No Admin Down ports found in the uploaded file.")

            if mapping_data or admin_data:
                st.markdown("---")
                st.markdown("### 📥 Download Results")
                txt_output = ""
                if mapping_data:
                    txt_output += "--- VLAN-wise IP and Subnet Mapping ---\n"
                    for item in mapping_data:
                        txt_output += f"Interface: {item['Interface/VLAN']}  |  IP: {item['IP Address']}  |  Subnet: {item['Subnet Mask (CIDR)']}\n"
                    txt_output += "\n"
                if admin_data:
                    txt_output += "--- Admin Down Ports ---\n"
                    for item in admin_data:
                        txt_output += f"Port: {item['Port']}  |  Status: {item['Status']}\n"
                        
                excel_io = io.BytesIO()
                with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                    if mapping_data:
                        df = pd.DataFrame(mapping_data)
                        df.to_excel(writer, sheet_name='VLAN_IP_Mapping', index=False)
                    if admin_data:
                        df = pd.DataFrame(admin_data)
                        df.to_excel(writer, sheet_name='Admin_Down_Ports', index=False)
                
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    st.download_button("📄 Download as .TXT", data=txt_output, file_name="parsed_router_results.txt", mime="text/plain", use_container_width=True)
                with dl_col2:
                    st.download_button("📊 Download as .EXCEL", data=excel_io.getvalue(), file_name="parsed_router_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# ----------------- TAB 2 -----------------
with tab2:
    st.markdown("### 🔄 Cross-Reference & MOP Generation")
    st.info("Upload your **Service Migration Excel Sheet** alongside your **Router Logs** (Parent AND Target). The app will cross-reference the SAPs, IPs, and dynamically validate port states before generating Deletion & Creation Scripts.")
    
    col1, col2 = st.columns(2)
    with col1:
        log_uploads = st.file_uploader("1. Upload Router Logs (Parent & Target)", type=["txt", "xlsx", "xls"], accept_multiple_files=True, key="tab2_log")
    with col2:
        excel_plan = st.file_uploader("2. Upload Migration Plan (XLSX)", type=["xlsx", "xls"], key="tab2_plan")
        
    if log_uploads and excel_plan:
        if st.button("🚀 Generate MOP Configurations", type="primary", use_container_width=True):
            st.markdown("---")
            
            all_lines = []
            for file in log_uploads:
                all_lines.extend(extract_lines_from_file(file))
            
            try:
                del_cfg, cre_cfg, warnings = generate_migration_configs(excel_plan, all_lines)
                
                if warnings:
                    for w in warnings:
                        st.error(f"🚨 **WARNING CLASH DETECTED:** {w} in the uploaded router logs!")
                        
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🗑️ Parent Node Deletion Script")
                    st.text_area("Review Deletion Commands:", value=del_cfg, height=400)
                    st.download_button("Download Deletion MOP (.txt)", data=del_cfg, file_name="parent_deletion_mop.txt", use_container_width=True)
                with c2:
                    st.subheader("🏗️ Target Node Creation Script")
                    st.text_area("Review Creation Commands:", value=cre_cfg, height=400)
                    st.download_button("Download Creation MOP (.txt)", data=cre_cfg, file_name="target_creation_mop.txt", use_container_width=True)
            except Exception as e:
                st.error(f"Failed to generate configurations: Are your excel columns named correctly? Error: {e}")
