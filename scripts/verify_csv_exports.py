import pandas as pd

print("=" * 60)
print("CSV VERIFICATION REPORT")
print("=" * 60)

# --- nodes.csv ---
nodes = pd.read_csv("E:/GL_AI/data_processed/graph_exports/nodes.csv")
print(f"\nNODES.CSV:")
print(f"  Total rows      : {len(nodes):,}")
print(f"  Total columns   : {len(nodes.columns)}")
print(f"  First 6 cols    : {list(nodes.columns[:6])}")
print(f"  Has node_id     : {'node_id' in nodes.columns}")
print(f"  Has node_id:ID  : {'node_id:ID' in nodes.columns}")
print(f"  Has props_json  : {'properties_json' in nodes.columns}")

# Label distribution
label_counts = nodes[":LABEL"].value_counts().head(15)
print(f"\n  Label distribution (top 15):")
for lbl, cnt in label_counts.items():
    print(f"    {lbl:<50} : {cnt}")

# Duplicate check
dup = nodes["node_id"].duplicated().sum()
print(f"\n  Duplicate node_ids  : {dup}")

# Sort check
is_sorted = nodes["node_id"].is_monotonic_increasing
print(f"  Sorted by node_id   : {is_sorted}")

print()
print("=" * 60)

# --- relationships.csv ---
rels = pd.read_csv("E:/GL_AI/data_processed/graph_exports/relationships.csv")
print(f"\nRELATIONSHIPS.CSV:")
print(f"  Total rows        : {len(rels):,}")
print(f"  Total columns     : {len(rels.columns)}")
print(f"  Has :START_ID     : {':START_ID' in rels.columns}")
print(f"  Has :END_ID       : {':END_ID' in rels.columns}")
print(f"  Has :TYPE         : {':TYPE' in rels.columns}")

# Empty ID check
empty_start = rels[":START_ID"].isna().sum()
empty_end = rels[":END_ID"].isna().sum()
print(f"  Empty :START_ID   : {empty_start}")
print(f"  Empty :END_ID     : {empty_end}")

# Relationship type distribution
type_counts = rels[":TYPE"].value_counts().head(15)
print(f"\n  Relationship type distribution (top 15):")
for t, cnt in type_counts.items():
    print(f"    {t:<45} : {cnt}")

# Sort check
is_sorted_rels = rels[":START_ID"].is_monotonic_increasing
print(f"\n  Sorted by :START_ID : {is_sorted_rels}")

# Cross-reference check: all START/END IDs exist in nodes
node_ids = set(nodes["node_id"].dropna())
missing_starts = rels[~rels[":START_ID"].isin(node_ids)][":START_ID"].dropna()
missing_ends = rels[~rels[":END_ID"].isin(node_ids)][":END_ID"].dropna()
print(f"\n  Dangling :START_IDs : {len(missing_starts)}")
print(f"  Dangling :END_IDs   : {len(missing_ends)}")
if len(missing_starts) > 0:
    print(f"    Examples: {list(missing_starts.unique()[:5])}")
if len(missing_ends) > 0:
    print(f"    Examples: {list(missing_ends.unique()[:5])}")

print()
print("=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
