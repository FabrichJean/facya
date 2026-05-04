import face_recognition
import os
import sys
import numpy as np
from PIL import Image
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pickle

# Cache pour les encodages des créateurs
CACHE_FILE = 'createurs_cache.pkl'
encodages_cache = {}

def charger_cache():
    """Charger le cache des encodages"""
    global encodages_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'rb') as f:
                encodages_cache = pickle.load(f)
            print("✅ Cache chargé")
        except:
            encodages_cache = {}
    return encodages_cache

def sauvegarder_cache():
    """Sauvegarder le cache des encodages"""
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(encodages_cache, f)
    print("💾 Cache sauvegardé")

def analyser_couleur_peau(image, face_location):
    """Extrait la couleur de peau dominante d'un visage"""
    top, right, bottom, left = face_location
    visage = image[top:bottom, left:right]
    
    if len(visage) == 0:
        return None
    
    couleur_moyenne = np.mean(visage, axis=(0, 1))
    return couleur_moyenne

def comparer_couleur_peau(couleur1, couleur2):
    """Compare deux couleurs de peau"""
    if couleur1 is None or couleur2 is None:
        return 0.5
    
    distance = np.sqrt(np.sum((couleur1 - couleur2) ** 2))
    similarity = 1 - (distance / (255 * np.sqrt(3)))
    return max(0, min(1, similarity))

def preparer_createur(chemin_ref):
    """Prépare et cache les données d'un créateur"""
    try:
        # Vérifier le cache d'abord
        if chemin_ref in encodages_cache:
            return chemin_ref, encodages_cache[chemin_ref]
        
        image_ref = face_recognition.load_image_file(chemin_ref)
        face_locations_ref = face_recognition.face_locations(image_ref)
        encodages_ref = face_recognition.face_encodings(image_ref, face_locations_ref)
        
        if not encodages_ref:
            return None, None
        
        # Sauvegarder dans le cache
        data = {
            'encodage': encodages_ref[0],
            'location': face_locations_ref[0],
            'image': image_ref
        }
        encodages_cache[chemin_ref] = data
        
        return chemin_ref, data
    except:
        return None, None

def comparer_createur(encodage_inconnu, location_inconnu, couleur_couv, chemin_ref, data_ref):
    """Compare un créateur avec le visage inconnu"""
    if data_ref is None:
        return None
    
    try:
        distance_faciale = face_recognition.face_distance(
            [data_ref['encodage']], 
            encodage_inconnu
        )[0]
        similarite_facial = 1 - distance_faciale
        
        couleur_visage_ref = analyser_couleur_peau(data_ref['image'], data_ref['location'])
        similarite_couleur = comparer_couleur_peau(couleur_couv, couleur_visage_ref)
        
        score_total = (similarite_facial * 0.7) + (similarite_couleur * 0.3)
        
        nom_createur = os.path.splitext(os.path.basename(chemin_ref))[0]
        
        return {
            'nom': nom_createur,
            'score': score_total,
            'distance': float(distance_faciale),
            'couleur': similarite_couleur,
            'facial': similarite_facial
        }
    except:
        return None

def trouver_createurs_sur_image(image_couverture_path, dossier_references, num_threads=4):
    """Trouve les créateurs avec traitement parallèle"""
    print("🚀 Démarrage de l'analyse avec traitement parallèle...")
    
    # 1. Charger l'image de couverture
    image_couv = face_recognition.load_image_file(image_couverture_path)
    face_locations_couv = face_recognition.face_locations(image_couv)
    encodings_couv = face_recognition.face_encodings(image_couv, face_locations_couv)
    
    if not encodings_couv:
        print("❌ Aucun visage trouvé dans l'image")
        return []
    
    # 2. Préparer tous les créateurs en parallèle
    print("📁 Préparation des encodages des créateurs...")
    fichiers_ref = [
        os.path.join(dossier_references, f) 
        for f in os.listdir(dossier_references) 
        if os.path.isfile(os.path.join(dossier_references, f))
    ]
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(preparer_createur, f): f for f in fichiers_ref}
        createurs_data = {}
        for future in as_completed(futures):
            chemin, data = future.result()
            if data is not None:
                createurs_data[chemin] = data
    
    print(f"✅ {len(createurs_data)} créateurs préparés")
    
    # 3. Comparer chaque visage avec tous les créateurs en parallèle
    scores_createurs = {}
    
    for idx_visage, (encodage_inconnu, location_inconnu) in enumerate(zip(encodings_couv, face_locations_couv)):
        print(f"\n🔍 Analyse du visage {idx_visage + 1}/{len(encodings_couv)}...")
        couleur_visage_couv = analyser_couleur_peau(image_couv, location_inconnu)
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {
                executor.submit(
                    comparer_createur, 
                    encodage_inconnu, 
                    location_inconnu, 
                    couleur_visage_couv,
                    chemin,
                    data
                ): chemin 
                for chemin, data in createurs_data.items()
            }
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    nom = result['nom']
                    if nom not in scores_createurs or result['score'] > scores_createurs[nom]['score']:
                        scores_createurs[nom] = {
                            'score': result['score'],
                            'distance': result['distance'],
                            'couleur': result['couleur'],
                            'facial': result['facial']
                        }
    
    # 4. Filtrer et trier
    seuil_minimum = 0.4
    resultats_filtres = {
        createur: infos for createur, infos in scores_createurs.items()
        if infos['score'] >= seuil_minimum
    }
    
    resultats_tries = sorted(resultats_filtres.items(), key=lambda x: x[1]['score'], reverse=True)
    
    # 5. Afficher les résultats
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
        
        # Sauvegarder le cache
        sauvegarder_cache()
    
    return list(set([createur for createur, _ in resultats_tries]))

if __name__ == "__main__":
    charger_cache()
    
    if len(sys.argv) < 2:
        print("Usage: python main.py <chemin_image_couverture>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    resultats = trouver_createurs_sur_image(image_path, "createurs/", num_threads=4)
    
    if resultats:
        print(f"\n🎯 Créateurs identifiés : {', '.join(resultats)}")
    else:
        print("\n❌ Aucun créateur identifié")
