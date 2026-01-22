import os, zipfile

def zipdir(path, zip):
    folder = os.path.basename(path)
    strip = path.replace(os.sep + folder, '')
    for root, dirs, files in os.walk(path):
        for file in files:
            zip.write(os.path.join(root, file), os.path.join(root.replace(strip, ''), file))

outdir = os.path.join('output', 'downloads')
os.makedirs(outdir, exist_ok=True)

for lang in ['en', 'de', 'hu']:
    print(f'creating ENARIS_{lang}.zip')
    zip = zipfile.ZipFile(os.path.join(outdir, f'ENARIS_{lang}.zip'), 'w', zipfile.ZIP_DEFLATED)
    zipdir(os.path.join('output', 'assets'), zip)
    zipdir(os.path.join('output', lang), zip)
    zip.close()

print('creating ENARIS_source.zip')
zip = zipfile.ZipFile(os.path.join(outdir, 'ENARIS_source.zip'), 'w', zipfile.ZIP_DEFLATED)
zipdir(os.path.join('.', 'data'), zip)
zipdir(os.path.join('.', 'templates'), zip)
zip.write('build.py')
zip.write('createpdfs.py')
zip.write('createzips.py')
zip.close()