import os
import pandas as pd
pd.set_option("display.max_columns", None)

folder = "ems_synthetic_data_strong"
tables = {}          # a dictionary: table name -> pandas table

for name in os.listdir(folder):
    if not name.endswith(".csv"):
        continue
    table_name = name[:-4]
    tables[table_name] = pd.read_csv(os.path.join(folder, name))
    print(f"{table_name}: {len(tables[table_name])} rows")

# Look at one table
print(tables["BREAKDOWN"].head())