#!/usr/bin/env pwsh
# Start the CommitmentOS API server
# Run from the project root: .\scripts\start_api.ps1

$env:PYTHONPATH = "$PSScriptRoot\..\apps\api;$PSScriptRoot\.."

Set-Location "$PSScriptRoot\..\apps\api"

Write-Host "Starting CommitmentOS API on http://localhost:8000" -ForegroundColor Green
Write-Host "Connected to database configured in .env (Supabase)" -ForegroundColor Cyan

uvicorn main:app --reload --host 0.0.0.0 --port 8000
