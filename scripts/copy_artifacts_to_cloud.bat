@echo off
REM Copy Artifacts to Cloud Storage

echo ============================================================
echo COPYING ARTIFACTS TO CLOUD STORAGE
echo ============================================================

set CLOUD_BASE=E:\GL_AI_Cloud\GL_AI

echo.
echo Creating cloud directory: %CLOUD_BASE%
mkdir "%CLOUD_BASE%" 2>nul
echo Done

REM Copy chroma_db
echo.
echo Checking for chroma_db...
if exist "chroma_db\" (
    echo Found chroma_db
    echo Copying to %CLOUD_BASE%\chroma_db...
    xcopy /E /I /Y "chroma_db" "%CLOUD_BASE%\chroma_db" >nul
    echo Copied
) else (
    echo Missing: chroma_db
)

REM Copy entity_registry.json
echo.
echo Checking for entity_registry.json...
if exist "entity_registry.json" (
    echo Found entity_registry.json
    echo Copying to %CLOUD_BASE%\entity_registry.json...
    copy /Y "entity_registry.json" "%CLOUD_BASE%\entity_registry.json" >nul
    echo Copied
) else (
    echo Missing: entity_registry.json
)

REM Copy chunks_export.json
echo.
echo Checking for chunks_export.json...
if exist "chunks_export.json" (
    echo Found chunks_export.json
    echo Copying to %CLOUD_BASE%\chunks_export.json...
    copy /Y "chunks_export.json" "%CLOUD_BASE%\chunks_export.json" >nul
    echo Copied
) else (
    echo Missing: chunks_export.json
)

echo.
echo ============================================================
echo COPY COMPLETE
echo ============================================================
echo.
echo Artifacts location: %CLOUD_BASE%
echo.
echo Next steps:
echo 1. Import to Neo4j: python scripts/setup_neo4j_from_cloud.py
echo 2. Test RAG QA: python scripts/demo_rag_qa.py
echo.
