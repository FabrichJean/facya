import face_recognition
import os
import sys

def trouver_createurs_sur_image(image_couverture_path, dossier_references):
    # 1. Charger l'image de couverture et trouver les visages
    image_couv = face_recognition.load_image_file(image_couverture_path)
    encodings_couv = face_recognition.face_encodings(image_couv)
    
    createurs_detectes = []

    # 2. Boucler sur chaque visage trouvé dans la couverture
    for encodage_inconnu in encodings_couv:
        
        # Comparer avec chaque fichier dans le dossier de référence
        for nom_fichier in os.listdir(dossier_references):
            chemin_ref = os.path.join(dossier_references, nom_fichier)
            
            # Charger la photo du créateur connu
            image_ref = face_recognition.load_image_file(chemin_ref)
            # On récupère le premier visage trouvé dans l'image de référence
            encodage_ref = face_recognition.face_encodings(image_ref)[0]

            # 3. Comparaison (tolerance 0.6 est le standard, plus bas c'est plus strict)
            match = face_recognition.compare_faces([encodage_ref], encodage_inconnu, tolerance=0.5)
            
            if match[0]:
                nom_createur = os.path.splitext(nom_fichier)[0]
                createurs_detectes.append(nom_createur)
                break # On a trouvé qui c'est, on passe au visage suivant sur la couv

    return list(set(createurs_detectes))

# Utilisation
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <chemin_image_couverture>")
        print("Exemple: python main.py couverture.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    resultats = trouver_createurs_sur_image(image_path, "createurs/")
    print(f"Créateurs identifiés : {', '.join(resultats)}")
