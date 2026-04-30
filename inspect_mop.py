import sys
import os
import pandas as pd
pd.set_option("display.max_rows", 200)

sys.path.append(r"C:\Users\Administrator\.gemini\antigravity\scratch\Nokia_Router_Tool")
from nokia_parser import generate_migration_configs

def main():
    base_dir = r"C:\Users\Administrator\OneDrive\Desktop\Nokia_Router_Tool\sample input & output"
    input_file = os.path.join(base_dir, "migration_input_template (1).xlsx")
    log_file = os.path.join(base_dir, "newfile.txt")

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            log_lines = f.read().splitlines()
        
        df_gen_auto, df_gen_manual, warnings = generate_migration_configs(input_file, log_lines)
        
        print("=== GENERATED AUTO MOP ROW 0 TO 150 ===")
        # Replace empty strings with "<BLANK>" so we can visibly see gaps.
        df_visible = df_gen_auto.replace("", "<BLANK>")
        print(df_visible.to_string())

    except Exception as e:
        print("Failed logic:", e)

if __name__ == "__main__":
    main()
