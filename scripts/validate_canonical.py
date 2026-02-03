import pandas as pd
from pathlib import Path

canonical_dir = Path("nlp_clin/data/vocab/canonical")

print("=" * 60)
print("VALIDACAO DA CAMADA CANONICAL")
print("=" * 60)

# 1. Verificar que todos os arquivos existem
files = ["concepts.csv", "entries.csv", "blocked_terms.csv", "ambiguity.csv", "metadata.yaml"]
for f in files:
    path = canonical_dir / f
    if path.exists():
        size = path.stat().st_size / 1024
        print(f"[OK] {f} ({size:.1f} KB)")
    else:
        print(f"[ERRO] {f} AUSENTE")

print("\n" + "=" * 60)

# 2. Validar concepts.csv
print("\nCONCEPTS.CSV")
df_concepts = pd.read_csv(canonical_dir / "concepts.csv")
print(f"  Total: {len(df_concepts)} conceitos")
print(f"  Colunas: {list(df_concepts.columns)}")
print(f"\n  Por vocabulário:")
print(df_concepts['vocabulary'].value_counts())
print(f"\n  Duplicatas em concept_id: {df_concepts['concept_id'].duplicated().sum()}")

# 3. Validar entries.csv
print("\n" + "=" * 60)
print("\nENTRIES.CSV")
df_entries = pd.read_csv(canonical_dir / "entries.csv")
print(f"  Total: {len(df_entries)} entries")
print(f"  Colunas: {list(df_entries.columns)}")
print(f"\n  Por tipo:")
print(df_entries['entry_type'].value_counts())
print(f"\n  Por match_policy:")
print(df_entries['match_policy'].value_counts())

# 4. Validar integridade referencial
print("\n" + "=" * 60)
print("\nINTEGRIDADE REFERENCIAL")
concepts_ids = set(df_concepts['concept_id'])
entry_concept_ids = set(df_entries['concept_id'])
orphan_entries = entry_concept_ids - concepts_ids
if orphan_entries:
    print(f"  [ERRO] {len(orphan_entries)} entries orfaos (sem concept_id correspondente)")
    print(f"     Exemplos: {list(orphan_entries)[:5]}")
else:
    print(f"  [OK] Todos os entries apontam para concepts validos")

# 5. Amostras de qualidade
print("\n" + "=" * 60)
print("\nAMOSTRAS DE QUALIDADE")

print("\n  CID-10 (5 primeiros):")
cid = df_concepts[df_concepts['vocabulary'] == 'CID10'].head()
for _, row in cid.iterrows():
    print(f"    {row['concept_id']}: {row['concept_name']}")

print("\n  TUSS_PROC (5 primeiros):")
tuss_p = df_concepts[df_concepts['vocabulary'] == 'TUSS_PROC'].head()
for _, row in tuss_p.iterrows():
    print(f"    {row['concept_id']}: {row['concept_name']}")

print("\n  LABS (5 primeiros):")
labs = df_concepts[df_concepts['vocabulary'] == 'LABS'].head()
for _, row in labs.iterrows():
    print(f"    {row['concept_id']}: {row['concept_name']}")

# 6. Verificar ambiguity.csv
print("\n" + "=" * 60)
print("\nAMBIGUITY.CSV")
df_amb = pd.read_csv(canonical_dir / "ambiguity.csv")
print(f"  Total: {len(df_amb)} registros de ambiguidade")
if len(df_amb) > 0:
    print(f"\n  Primeiros 5:")
    print(df_amb.head()[['entry_text', 'possible_meanings']])

# 7. Verificar blocked_terms.csv
print("\n" + "=" * 60)
print("\nBLOCKED_TERMS.CSV")
df_blocked = pd.read_csv(canonical_dir / "blocked_terms.csv")
print(f"  Total: {len(df_blocked)} termos bloqueados")
if len(df_blocked) > 0:
    print(f"\n  Primeiros 10:")
    for _, row in df_blocked.head(10).iterrows():
        print(f"    {row['term']}: {row.get('reason', 'N/A')}")

print("\n" + "=" * 60)
print("VALIDACAO COMPLETA")
print("=" * 60)
