@echo off

echo Running city_net.py
python src\city_net.py

echo Running city_area.py
python src\city_area.py

echo Running city_pois.py
python src\city_pois.py

echo Running city_zensus.py
python src\city_zensus.py

echo Batch execution complete