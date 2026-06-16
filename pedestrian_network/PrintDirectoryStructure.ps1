# PowerShell script to print a formatted directory structure to a text file
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
        $subdirectories = Get-ChildItem -LiteralPath $path | Where-Object { $_.PSIsContainer -and $_.Name -notin $excludedDirectories }

        # Write items with appropriate indentation and formatting to the file
        foreach ($subdir in $subdirectories) {
            # Recursively call the function for subdirectories
            Print-DirectoryStructure -path $subdir.FullName -indentLevel ($indentLevel + 1) -outputFile $outputFile
        }

        # Get Python files in the directory
        $pyFiles = Get-ChildItem -LiteralPath $path -Filter *.py | Where-Object { -not $_.PSIsContainer }

        # Write Python files with appropriate indentation to the file
        foreach ($pyFile in $pyFiles) {
            "$('    ' * ($indentLevel + 1))|-- $($pyFile.Name)" | Out-File -Append -LiteralPath $outputFile
        }

        # Get CSV files in the directory
        $csvFiles = Get-ChildItem -LiteralPath $path -Filter *.csv | Where-Object { -not $_.PSIsContainer }

        # Write CSV files with appropriate indentation to the file
        foreach ($csvFile in $csvFiles) {
            "$('    ' * ($indentLevel + 1))|-- $($csvFile.Name)" | Out-File -Append -LiteralPath $outputFile
        }
    }
    catch {
        "$('    ' * ($indentLevel + 1))|-- Error: $_" | Out-File -Append -LiteralPath $outputFile
    }
}

# Example usage with output to a file
Print-DirectoryStructure -path "C:\Users\Goerner\Desktop\pedestrian_network" -outputFile "DirectoryStructureOutput.txt"
