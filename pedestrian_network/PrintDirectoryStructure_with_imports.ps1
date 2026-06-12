function Print-DirectoryStructure {
    param (
        [string]$path = ".",
        [int]$indentLevel = 0,
        [string]$outputFile = "DirectoryStructure.txt"
    )

    # Excluded directories
    $excludedDirectories = @("venv", "__pycache__")

    # Write the formatted path to the file with increased indentation
    "$('    ' * $indentLevel)|-- $($path | Split-Path -Leaf)" | Out-File -Append -LiteralPath $outputFile

    try {
        # Get immediate subdirectories in the directory excluding specified ones
        $subdirectories = Get-ChildItem -LiteralPath $path -Directory | Where-Object { $_.Name -notin $excludedDirectories }

        # Write items with appropriate indentation and formatting to the file
        foreach ($subdir in $subdirectories) {
            # Recursively call the function for subdirectories
            Print-DirectoryStructure -path $subdir.FullName -indentLevel ($indentLevel + 1) -outputFile $outputFile
        }

        # Get Python files in the directory
        $pyFiles = Get-ChildItem -LiteralPath $path -Filter *.py | Where-Object { -not $_.PSIsContainer }

        # Write Python files and their imports with appropriate indentation to the file
        foreach ($pyFile in $pyFiles) {
            # File name
            $fileIndent = $('    ' * ($indentLevel + 1))
            "$fileIndent|-- $($pyFile.Name)" | Out-File -Append -LiteralPath $outputFile

            # Attempt to read file and find import statements
            $filePath = Join-Path -Path $path -ChildPath $pyFile.Name
            $fileContent = Get-Content -Path $filePath -ErrorAction SilentlyContinue
            $imports = $fileContent | Where-Object { $_ -match '^\s*(from|import)\s' }

            # Write import statements
            foreach ($import in $imports) {
                "$fileIndent    |-- $import" | Out-File -Append -LiteralPath $outputFile
            }
        }

        # Get CSV files in the directory
        $csvFiles = Get-ChildItem -LiteralPath $path -Filter *.csv | Where-Object { -not $_.PSIsContainer }

        # Write CSV files with appropriate indentation to the file
        foreach ($csvFile in $csvFiles) {
            "$('    ' * ($indentLevel + 1))|-- $($csvFile.Name)" | Out-File -Append -LiteralPath $outputFile
        }
    }
    catch {
        # Error handling with more specific error information
        "$('    ' * ($indentLevel + 1))|-- Error: $($_.Exception.Message)" | Out-File -Append -LiteralPath $outputFile
    }
}

# Example usage with output to a file
Print-DirectoryStructure -path "C:\Users\Goerner\Desktop\pedestrian_network" -outputFile "DirectoryStructureOutput2.txt"
