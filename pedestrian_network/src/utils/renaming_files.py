import os


def umbenennen_ordner_dateien(ordner_pfad, muster_liste, neuer_muster):
    """
    Umbenennt alle Dateien im angegebenen Ordner entsprechend einem der Muster in der Liste.
    
    Args:
        ordner_pfad (str): Pfad zum Ordner mit den Dateien.
        muster_liste (list): Liste von Mustern, die in den Dateinamen gesucht werden.
        neuer_muster (str): Neues Muster, das vor dem Stadtnamen steht.
    """
    for datei_name in os.listdir(ordner_pfad):
        datei_pfad = os.path.join(ordner_pfad, datei_name)
        if os.path.isfile(datei_pfad) and datei_name.endswith(".gpkg"):
            for muster in muster_liste:
                if muster in datei_name:
                    teile = datei_name.split("_")
                    stadt_name = teile[-1].split(".")[0]
                    neuer_datei_name = f"{stadt_name}_{neuer_muster}.gpkg"
                    neuer_datei_pfad = os.path.join(ordner_pfad, neuer_datei_name)
                    os.rename(datei_pfad, neuer_datei_pfad)
                    break  # Sobald ein passendes Muster gefunden wurde, brechen wir die Schleife ab

def main():
    ordner_pfad = r"data\output"
    muster_liste = ["street_net_optimized_updated", "osm_pois_updated","osm_area_updated", "node_points" ]
    neuer_muster = input("Gib das neue Muster ein, das vor dem Stadtnamen stehen soll: ")

    umbenennen_ordner_dateien(ordner_pfad, muster_liste, neuer_muster)
    print("Umbenennung abgeschlossen.")

if __name__ == "__main__":
    main()