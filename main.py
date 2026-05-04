import face_recognition
import os
import sys
import numpy as np
from PIL import Image

def analyser_couleur_peau(image, face_location):
    """Extrait la couleur de peau dominante d'un visage"""
    top, right, bottom, left = face_location
    # Extraire la région du visage
    visage = image[top:bottom, left:right]
    
    # Convertir en RGB et calculer la moyenne des pixels
    if len(visage) == 0:
        return None
    
    # Moyenne des canaux RGB
    couleur_moyenne = np.mean(visage, axis=(0, 1))
    return couleur_moyenne

def comparer_couleur_peau(couleur1, couleur2):
    """Compare deux couleurs de peau, retourne une similarité entre 0 et 1"""
    if couleur1 is None or couleur2 is None:
        return 0.5
    
    # Distance euclidienne normalisée
    distance = np.sqrt(np.sum((couleur1 - couleur2) ** 2))
    # Normaliser entre 0 et 1 (255*sqrt(3) est la distance max)
    similarity = 1 - (distance / (255 * np.sqrt(3)))
    return max(0, min(1, similarity))

def trouver_createurs_sur_image(image_couverture_path, dossier_references):
    # 1. Charger l'image de couverture et trouver les visages
    image_couv = face_recognition.load_image_file(image_couverture_path)
    face_locations_couv = face_recognition.face_locations(image_couv)
    encodings_couv = face_recognition.face_encodings(image_couv, face_locations_couv)
    
    createurs_detectes = []
    scores_createurs = {}  # Dictionnaire pour stocker les meilleurs scores

    # 2. Boucler sur chaque visage trouvé dans la couverture
    for idx_visage, (encodage_inconnu, location_inconnu) in enumerate(zip(encodings_couv, face_locations_couv)):
        couleur_visage_couv = analyser_couleur_peau(image_couv, location_inconnu)
        
        # Comparer avec chaque fichier dans le dossier de référence
        for nom_fichier in os.listdir(dossier_references):
            chemin_ref = os.path.join(dossier_references, nom_fichier)
            
            # Vérifier que c'est un fichier image
            if not os.path.isfile(chemin_ref):
                continue
            
            try:
                # Charger la photo du créateur connu
                image_ref = face_recognition.load_image_file(chemin_ref)
                face_locations_ref = face_recognition.face_locations(image_ref)
                # On récupère le premier visage trouvé dans l'image de référence
                encodages_ref = face_recognition.face_encodings(image_ref, face_locations_ref)
                
                if not encodages_ref:
                    continue
                
                encodage_ref = encodages_ref[0]
                location_ref = face_locations_ref[0]

                # 3. Comparaison multi-critères
                # a) Distance faciale (plus proche = mieux)
                distance_faciale = face_recognition.face_distance([encodage_ref], encodage_inconnu)[0]
                similarite_facial = 1 - distance_faciale  # Inverser pour avoir 0-1
                
                # b) Comparaison de couleur de peau
                couleur_visage_ref = analyser_couleur_peau(image_ref, location_ref)
                similarite_couleur = comparer_couleur_peau(couleur_visage_couv, couleur_visage_ref)
                
                # c) Score combiné (moyenne pondérée)
                # 70% reconnaissance faciale, 30% couleur de peau
                score_total = (similarite_facial * 0.7) + (similarite_couleur * 0.3)
                
                nom_createur = os.path.splitext(nom_fichier)[0]
                
                # Garder le meilleur score pour chaque créateur
                if nom_createur not in scores_createurs or score_total > scores_createurs[nom_createur]['score']:
                    scores_createurs[nom_createur] = {
                        'score': score_total,
                        'distance': distance_faciale,
                        'couleur': similarite_couleur,
                        'facial': similarite_facial
                    }
                    
            except Exception as e:
                continue
    
    # 4. Filtrer les résultats avec un seuil minimum et les trier par score
    seuil_minimum = 0.4  # Accepter les matches avec un score >= 0.4
    resultats_filtres = {
        createur: infos for createur, infos in scores_createurs.items()
        if infos['score'] >= seuil_minimum
    }
    
    # Trier par score décroissant
    resultats_tries = sorted(resultats_filtres.items(), key=lambda x: x[1]['score'], reverse=True)
    
    # Afficher les résultats détaillés
    if resultats_tries:
        print("\n📊 Résultats de la reconnaissance faciale:")
        print("-" * 70)
        for createur, infos in resultats_tries:
            print(f"✅ {createur}")
            print(f"   Score global: {infos['score']:.2%}")
            print(f"   - Ressemblance faciale: {infos['facial']:.2%}")
            print(f"   - Ressemblance couleur peau: {infos['couleur']:.2%}")
            print(f"   - Distance faciale: {infos['distance']:.4f}")
        print("-" * 70)
    
    return list(set([createur for createur, _ in resultats_tries]))

# Utilisation
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <chemin_image_couverture>")
        print("Exemple: python main.py couverture.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    resultats = trouver_createurs_sur_image(image_path, "createurs/")
    
    if resultats:
        print(f"\n🎯 Créateurs identifiés : {', '.join(resultats)}")
    else:
        print("\n❌ Aucun créateur identifié")
