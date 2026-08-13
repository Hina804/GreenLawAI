with open('src/ui/portal.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 1051 to 1499 (1-indexed) are indices 1050 to 1498 (0-indexed)
uncommented_count = 0
for idx in range(1050, 1499):
    line = lines[idx]
    if line.startswith('# '):
        lines[idx] = line[2:]
        uncommented_count += 1
    elif line.startswith('#'):
        lines[idx] = line[1:]
        uncommented_count += 1

# Let's clean the Judiciary title emoji if present
for idx in range(1050, 1499):
    if 'st.title(' in lines[idx] and '🏛️' in lines[idx]:
        lines[idx] = lines[idx].replace('🏛️ ', '').replace('🏛️', '')

with open('src/ui/portal.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Successfully uncommented {uncommented_count} lines and cleaned emojis!")
