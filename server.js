const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const app = express();
const PORT = 3000;

// Configuration multer pour les uploads
const upload = multer({
  dest: 'uploads/',
  fileFilter: (req, file, cb) => {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Type de fichier non supporté'));
    }
  }
});

// Middleware
app.use(express.static('public'));
app.use(express.json());

// Route pour servir l'interface
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Route pour l'upload et le matching
app.post('/api/match', upload.single('image'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'Aucun fichier fourni' });
  }

  const imagePath = req.file.path;

  // Exécuter le script Python
  const python = spawn('python3', ['main.py', imagePath]);

  let output = '';
  let errorOutput = '';

  python.stdout.on('data', (data) => {
    output += data.toString();
  });

  python.stderr.on('data', (data) => {
    errorOutput += data.toString();
  });

  python.on('close', (code) => {
    // Nettoyer le fichier uploadé
    fs.unlink(imagePath, (err) => {
      if (err) console.error('Erreur lors de la suppression du fichier:', err);
    });

    if (code !== 0) {
      return res.status(500).json({
        error: 'Erreur lors de l\'analyse de l\'image',
        details: errorOutput
      });
    }

    // Parser la sortie du script Python
    const lines = output.split('\n');
    const createurs = [];
    let details = '';

    // Chercher la ligne avec "Créateurs identifiés"
    for (let line of lines) {
      if (line.includes('Créateurs identifiés')) {
        const match = line.match(/Créateurs identifiés : (.+)/);
        if (match && match[1]) {
          const creatorsStr = match[1].trim();
          if (creatorsStr !== '') {
            createurs.push(...creatorsStr.split(', '));
          }
        }
      }
    }

    res.json({
      success: true,
      createurs: createurs.length > 0 ? createurs : [],
      details: output
    });
  });
});

// Créer les dossiers nécessaires
if (!fs.existsSync('uploads')) {
  fs.mkdirSync('uploads');
}
if (!fs.existsSync('public')) {
  fs.mkdirSync('public');
}

// Démarrer le serveur
app.listen(PORT, () => {
  console.log(`✅ Serveur démarré sur http://localhost:${PORT}`);
  console.log(`📝 Interface disponible à: http://localhost:${PORT}`);
});
