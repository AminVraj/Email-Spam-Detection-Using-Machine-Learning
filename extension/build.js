const fs = require('fs');
const path = require('path');

function copyFileSync(source, target) {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(source, target);
}

function copyFolderRecursiveSync(source, target) {
    if (!fs.existsSync(source)) {
        return;
    }

    if (!fs.existsSync(target)) {
        fs.mkdirSync(target, { recursive: true });
    }

    for (const file of fs.readdirSync(source)) {
        const sourcePath = path.join(source, file);
        const targetPath = path.join(target, file);

        if (fs.lstatSync(sourcePath).isDirectory()) {
            copyFolderRecursiveSync(sourcePath, targetPath);
        } else {
            copyFileSync(sourcePath, targetPath);
        }
    }
}

// Create dist directory if it does not exist.
// IMPORTANT: Do NOT delete dist here.
// TypeScript has already generated the compiled JavaScript files.
fs.mkdirSync('dist', { recursive: true });

// Copy manifest
copyFileSync(
    'manifest.json',
    'dist/manifest.json'
);

// Copy popup static assets
copyFileSync(
    'src/popup/popup.html',
    'dist/popup/popup.html'
);

copyFileSync(
    'src/popup/popup.css',
    'dist/popup/popup.css'
);

// Copy icons if they exist
if (fs.existsSync('icons')) {
    copyFolderRecursiveSync(
        'icons',
        'dist/icons'
    );
}

console.log('Build output copied to dist/');