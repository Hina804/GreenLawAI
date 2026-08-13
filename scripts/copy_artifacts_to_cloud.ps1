# Copy Artifacts to Cloud Storage
# This script copies existing artifacts to E:/GL_AI_Cloud/GL_AI/

$cloudBase = "E:\GL_AI_Cloud\GL_AI"

Write-Host "="*60
Write-Host "COPYING ARTIFACTS TO CLOUD STORAGE"
Write-Host "="*60

# Create base directory
Write-Host "`nCreating cloud directory: $cloudBase"
New-Item -ItemType Directory -Force -Path $cloudBase | Out-Null
Write-Host "✓ Directory created"

# Check and copy chroma_db
Write-Host "`nChecking for chroma_db..."
if (Test-Path "chroma_db") {
    Write-Host "✓ Found chroma_db"
    Write-Host "  Copying to $cloudBase\chroma_db..."
    Copy-Item -Path "chroma_db" -Destination "$cloudBase\chroma_db" -Recurse -Force
    Write-Host "  ✓ Copied"
} else {
    Write-Host "✗ chroma_db not found"
}

# Check and copy entity_registry.json
Write-Host "`nChecking for entity_registry.json..."
if (Test-Path "entity_registry.json") {
    Write-Host "✓ Found entity_registry.json"
    Write-Host "  Copying to $cloudBase\entity_registry.json..."
    Copy-Item -Path "entity_registry.json" -Destination "$cloudBase\entity_registry.json" -Force
    Write-Host "  ✓ Copied"
} else {
    Write-Host "✗ entity_registry.json not found"
}

# Check and copy chunks_export.json
Write-Host "`nChecking for chunks_export.json..."
if (Test-Path "chunks_export.json") {
    Write-Host "✓ Found chunks_export.json"
    Write-Host "  Copying to $cloudBase\chunks_export.json..."
    Copy-Item -Path "chunks_export.json" -Destination "$cloudBase\chunks_export.json" -Force
    Write-Host "  ✓ Copied"
} else {
    Write-Host "✗ chunks_export.json not found"
}

# Summary
Write-Host "`n" + "="*60
Write-Host "COPY COMPLETE"
Write-Host "="*60
Write-Host "`nArtifacts location: $cloudBase"
Write-Host "`nNext steps:"
Write-Host "1. Import to Neo4j: python scripts/setup_neo4j_from_cloud.py"
Write-Host "2. Test RAG QA: python scripts/demo_rag_qa.py"
