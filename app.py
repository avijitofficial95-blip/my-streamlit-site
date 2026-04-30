import streamlit as st
import pandas as pd
import io
import xlsxwriter
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
    st.info("Upload your **Service Migration Excel Sheet** alongside your **Router Logs** (Parent AND Target). The app will cross-reference the SAPs, IPs, and map target configurations.")
    
    # Template Download
    try:
        # Dynamically generate the template to ensure valid strictly-formatted Excel file
        df_template = pd.DataFrame(columns=["site_id", "parent_router", "parent_port", "src_vlan", "target_vlan", "target_router", "target_port", "bandwidth"])
        
        # Proper handling of BytesIO buffer for Excel
        template_io = io.BytesIO()
        writer = pd.ExcelWriter(template_io, engine='xlsxwriter')
        df_template.to_excel(writer, sheet_name='Migration_Input', index=False)
        writer.close()
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            st.download_button(
                label="📥 Download Template (.xlsx)", 
                data=template_io.getvalue(), 
                file_name="migration_input_template.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                type="secondary",
                use_container_width=True
            )
        
        # Provide CSV version as a bulletproof alternative
        csv_data = df_template.to_csv(index=False).encode('utf-8')
        with col_down2:
            st.download_button(
                label="📥 Download Template (.csv)",
                data=csv_data,
                file_name="migration_input_template.csv",
                mime="text/csv",
                type="secondary",
                use_container_width=True
            )
    except Exception as e:
        st.warning(f"Template generation failed: {e}")

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
                df_auto, df_manual, warnings = generate_migration_configs(excel_plan, all_lines)
                
                if warnings:
                    for w in warnings:
                        st.error(f"🚨 **WARNING DETECTED:** {w}")

                st.success("MOP Generated Successfully!")
                st.write("Preview of Automation MOP (Head 10)")
                st.dataframe(df_auto.head(10), use_container_width=True)

                # Excel Generation with xlsxwriter
                excel_io = io.BytesIO()
                with pd.ExcelWriter(excel_io, engine='xlsxwriter') as writer:
                    df_auto.to_excel(writer, sheet_name='Automation MOP', index=False)
                    df_manual.to_excel(writer, sheet_name='Manual MOP', index=False, header=True)
                
                st.download_button(
                    label="📊 Download Final Output MOP (.XLSX)", 
                    data=excel_io.getvalue(), 
                    file_name="output_mop.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                    use_container_width=True,
                    type="primary"
                )
                
            except Exception as e:
                st.error(f"Failed to generate configurations: {e}")
