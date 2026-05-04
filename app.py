from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, disconnect
import face_recognition
import os
import sys
import numpy as np
from werkzeug.utils import secure_filename
import json
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'facya-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Créer le dossier uploads s'il n'existe pas
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyser_couleur_peau(image, face_location):
    """Extrait la couleur de peau dominante d'un visage"""
    top, right, bottom, left = face_location
    visage = image[top:bottom, left:right]
    
    if len(visage) == 0:
        return None
    
    couleur_moyenne = np.mean(visage, axis=(0, 1))
    return couleur_moyenne

def comparer_couleur_peau(couleur1, couleur2):
    """Compare deux couleurs de peau, retourne une similarité entre 0 et 1"""
    if couleur1 is None or couleur2 is None:
        return 0.5
    
    distance = np.sqrt(np.sum((couleur1 - couleur2) ** 2))
    similarity = 1 - (distance / (255 * np.sqrt(3)))
    return max(0, min(1, similarity))

def trouver_createurs_sur_image(image_couverture_path, dossier_references="createurs", socket_id=None):
    """Trouve les créateurs correspondant aux visages de l'image"""
    temps_debut = time.time()
    try:
        # Charger l'image de couverture et trouver les visages
        image_couv = face_recognition.load_image_file(image_couverture_path)
        face_locations_couv = face_recognition.face_locations(image_couv)
        encodings_couv = face_recognition.face_encodings(image_couv, face_locations_couv)
        
        if not encodings_couv:
            return {
                'success': False,
                'message': 'Aucun visage détecté dans l\'image',
                'resultats': [],
                'temps': 0
            }
        
        scores_createurs = {}
        fichiers_ref = [f for f in os.listdir(dossier_references) if os.path.isfile(os.path.join(dossier_references, f))]
        nombre_fichiers = len(fichiers_ref)
        total_comparaisons = len(encodings_couv) * nombre_fichiers
        comparaison_actuelle = 0
        
        # Boucler sur chaque visage trouvé dans la couverture
        for idx_visage, (encodage_inconnu, location_inconnu) in enumerate(zip(encodings_couv, face_locations_couv)):
            couleur_visage_couv = analyser_couleur_peau(image_couv, location_inconnu)
            
            # Comparer avec chaque fichier dans le dossier de référence
            for idx_fichier, nom_fichier in enumerate(fichiers_ref):
                chemin_ref = os.path.join(dossier_references, nom_fichier)
                
                try:
                    image_ref = face_recognition.load_image_file(chemin_ref)
                    face_locations_ref = face_recognition.face_locations(image_ref)
                    encodages_ref = face_recognition.face_encodings(image_ref, face_locations_ref)
                    
                    if not encodages_ref:
                        comparaison_actuelle += 1
                        continue
                    
                    encodage_ref = encodages_ref[0]
                    location_ref = face_locations_ref[0]
                    
                    # Comparaison multi-critères
                    distance_faciale = face_recognition.face_distance([encodage_ref], encodage_inconnu)[0]
                    similarite_facial = 1 - distance_faciale
                    
                    couleur_visage_ref = analyser_couleur_peau(image_ref, location_ref)
                    similarite_couleur = comparer_couleur_peau(couleur_visage_couv, couleur_visage_ref)
                    
                    # Score combiné
                    score_total = (similarite_facial * 0.7) + (similarite_couleur * 0.3)
                    
                    nom_createur = os.path.splitext(nom_fichier)[0]
                    
                    if nom_createur not in scores_createurs or score_total > scores_createurs[nom_createur]['score']:
                        # Encoder l'image en base64
                        import base64
                        with open(chemin_ref, 'rb') as f:
                            image_data = f.read()
                            image_base64 = base64.b64encode(image_data).decode('utf-8')
                        
                        scores_createurs[nom_createur] = {
                            'score': score_total,
                            'distance': float(distance_faciale),
                            'couleur': float(similarite_couleur),
                            'facial': float(similarite_facial),
                            'image': f'data:image/jpeg;base64,{image_base64}'
                        }
                    
                    comparaison_actuelle += 1
                    
                    # Envoyer la progression chaque N comparaisons
                    if comparaison_actuelle % 5 == 0 or comparaison_actuelle == total_comparaisons:
                        if socket_id:
                            progress = (comparaison_actuelle / total_comparaisons) * 100
                            
                            # Trier et envoyer les résultats courants
                            resultats_tries = sorted(
                                [(c, i) for c, i in scores_createurs.items() if i['score'] >= 0.4],
                                key=lambda x: x[1]['score'],
                                reverse=True
                            )
                            
                            socketio.emit('progress_update', {
                                'progress': round(progress, 1),
                                'processed': comparaison_actuelle,
                                'total': total_comparaisons,
                                'resultats': [
                                    {
                                        'nom': createur,
                                        'rank': idx + 1,
                                        'score': round(infos['score'] * 100, 2),
                                        'facial': round(infos['facial'] * 100, 2),
                                        'couleur': round(infos['couleur'] * 100, 2),
                                        'distance': round(infos['distance'], 4),
                                        'image': infos['image']
                                    }
                                    for idx, (createur, infos) in enumerate(resultats_tries[:5])  # Top 5 uniquement
                                ]
                            }, to=socket_id)
                        
                except Exception as e:
                    comparaison_actuelle += 1
                    continue
        
        # Résultats finaux
        seuil_minimum = 0.4
        resultats_filtres = {
            createur: infos for createur, infos in scores_createurs.items()
            if infos['score'] >= seuil_minimum
        }
        
        resultats_tries = sorted(resultats_filtres.items(), key=lambda x: x[1]['score'], reverse=True)
        
        # Calculer le temps écoulé
        temps_fin = time.time()
        temps_ecoule = temps_fin - temps_debut
        
        return {
            'success': True,
            'message': f'{len(resultats_tries)} créateur(s) trouvé(s)',
            'visages_detectes': len(encodings_couv),
            'temps': round(temps_ecoule, 2),
            'resultats': [
                {
                    'nom': createur,
                    'rank': idx + 1,
                    'score': round(infos['score'] * 100, 2),
                    'facial': round(infos['facial'] * 100, 2),
                    'couleur': round(infos['couleur'] * 100, 2),
                    'distance': round(infos['distance'], 4),
                    'image': infos['image']
                }
                for idx, (createur, infos) in enumerate(resultats_tries)
            ]
        }
        
    except Exception as e:
        temps_fin = time.time()
        temps_ecoule = temps_fin - temps_debut
        return {
            'success': False,
            'message': f'Erreur: {str(e)}',
            'temps': round(temps_ecoule, 2),
            'resultats': []
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Format de fichier non autorisé. Utilisez jpg, png, gif ou bmp'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Retourner juste le chemin, l'analyse se fera via WebSocket
        return jsonify({
            'success': True,
            'filepath': filepath,
            'message': 'Fichier reçu, analyse en cours...'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur lors du traitement: {str(e)}'}), 500

@app.route('/api/createurs', methods=['GET'])
def get_createurs():
    """Retourne la liste des créateurs disponibles"""
    dossier = 'createurs'
    if not os.path.exists(dossier):
        return jsonify([])
    
    createurs = []
    for fichier in os.listdir(dossier):
        if os.path.isfile(os.path.join(dossier, fichier)):
            nom = os.path.splitext(fichier)[0]
            chemin_image = os.path.join(dossier, fichier)
            # Encoder l'image en base64
            with open(chemin_image, 'rb') as f:
                image_data = f.read()
                import base64
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            createurs.append({
                'nom': nom,
                'image': f'data:image/jpeg;base64,{image_base64}'
            })
    
    return jsonify(sorted(createurs, key=lambda x: x['nom']))

@socketio.on('analyze')
def handle_analyze(data):
    """Traite l'analyse d'image avec WebSocket"""
    socket_id = request.sid
    
    if 'filepath' not in data:
        emit('error', {'message': 'Chemin de fichier manquant'})
        return
    
    filepath = data['filepath']
    
    try:
        # Lancer l'analyse dans un thread séparé
        thread = threading.Thread(
            target=lambda: _analyze_with_progress(filepath, socket_id)
        )
        thread.daemon = True
        thread.start()
    except Exception as e:
        emit('error', {'message': str(e)})

def _analyze_with_progress(filepath, socket_id):
    """Lance l'analyse avec progression"""
    try:
        resultats = trouver_createurs_sur_image(filepath, socket_id=socket_id)
        
        # Envoyer les résultats finaux
        socketio.emit('complete', resultats, to=socket_id)
        
        # Supprimer le fichier
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        socketio.emit('error', {'message': str(e)}, to=socket_id)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
