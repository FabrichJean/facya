const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const API_URL = 'http://192.168.1.97:3005/api/v1/creators/all';
const CDN_BASE_URL = 'http://192.168.1.97:3005/cdn?key=';
const CREATORS_DIR = path.join(__dirname, 'createurs');
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwicm9sZSI6InN1cGVyYWRtaW4iLCJlbWFpbCI6ImFuZHJpYW5haW5haGVudHNvYUBnbWFpbC5jb20iLCJ1c2VybmFtZSI6InN1cGVyYWRtaW4iLCJpc1ZhbGlkYXRlZCI6dHJ1ZSwiaWF0IjoxNzc3ODgwODYyLCJleHAiOjE3Nzc5NjcyNjJ9.j7JkLQMZOJ8fsGBhI9NfKbhxlzh4DEiKbURd65A91Ik';

// Créer le dossier s'il n'existe pas
if (!fs.existsSync(CREATORS_DIR)) {
  fs.mkdirSync(CREATORS_DIR, { recursive: true });
}

// Fonction pour télécharger un fichier
function downloadFile(url, filePath) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https') ? https : http;
    const file = fs.createWriteStream(filePath);

    protocol
      .get(url, (response) => {
        response.pipe(file);
        file.on('finish', () => {
          file.close();
          resolve();
        });
      })
      .on('error', (err) => {
        fs.unlink(filePath, () => {}); // Supprimer le fichier en cas d'erreur
        reject(err);
      });
  });
}

// Fonction pour fetcher les créateurs
async function fetchCreators() {
  try {
    console.log('📡 Fetching creators from API...');

    const response = await fetch(API_URL, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    const creators = data.creators || [];

    console.log(`✅ Found ${creators.length} creators`);

    // Télécharger les avatars
    for (let i = 0; i < creators.length; i++) {
      const creator = creators[i];
      
      if (!creator.avatar) {
        console.log(`⚠️  Creator ${creator.id} has no avatar`);
        continue;
      }

      const avatarUrl = `${CDN_BASE_URL}${encodeURIComponent(creator.avatar)}`;
      const fileExtension = path.extname(creator.avatar) || '.jpg';
      const fileName = `${creator.id}.png`;
      const filePath = path.join(CREATORS_DIR, fileName);

      try {
        console.log(`⬇️  Downloading avatar for creator ${creator.id} (${i + 1}/${creators.length})...`);
        await downloadFile(avatarUrl, filePath);
        console.log(`✅ Saved: ${fileName}`);
      } catch (error) {
        console.error(`❌ Failed to download avatar for creator ${creator.id}:`, error.message);
      }
    }

    console.log('\n🎉 All done!');
  } catch (error) {
    console.error('❌ Error fetching creators:', error);
    process.exit(1);
  }
}

// Lancer le script
fetchCreators();
