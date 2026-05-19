import png2icons from 'png2icons';
import fs from 'fs';
import path from 'path';

const SOURCE = process.argv[2] || 'electron/icon-source.png';
const OUTPUT = 'electron/icon.ico';

if (!fs.existsSync(SOURCE)) {
  console.error(`✗ ficheiro não encontrado: ${SOURCE}`);
  console.error(`  guarda a imagem como ${SOURCE} e corre novamente.`);
  process.exit(1);
}

const input  = fs.readFileSync(SOURCE);
const output = png2icons.createICO(input, png2icons.BICUBIC2, 0, true, false);

if (!output) {
  console.error('✗ falha ao gerar .ico (a imagem precisa ser PNG válido)');
  process.exit(1);
}

fs.writeFileSync(OUTPUT, output);
const kb = (output.length / 1024).toFixed(1);
console.log(`✓ ${OUTPUT} criado (${kb} KB) — sizes 16/24/32/48/64/128/256`);
