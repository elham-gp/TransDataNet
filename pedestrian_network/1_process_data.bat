@echo off

echo Running modules src\data\processing\distance_to_opnv.py
python src\data\modules\processing\distance_to_opnv.py

echo Running modules\processing\distance_to_education.py
python src\data\modules\src\data\processing\distance_to_education.py

echo Running final calculations

echo Running src\data\Varianten\Vorzugsvariante.py
python Var src\data\anten\Vorzugsvariante.py

echo Batch execution complete