// Print de conferência: node shot.js <url> <saida.png> [largura=1280] [pv-ID]
// Sem pv-ID tira a página inteira visível; com pv-ID abre e fotografa só aquele card.
// Precisa de puppeteer instalado na pasta de trabalho (npm init -y && npm i puppeteer) e do Chrome em /Applications.
const p = require('puppeteer');
(async () => {
  const [, , url, out, w = '1280', id] = process.argv;
  const b = await p.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const pg = await b.newPage();
  await pg.setViewport({ width: +w, height: 1600, deviceScaleFactor: 1 });
  await pg.goto(url, { waitUntil: 'networkidle0' });
  if (id) {
    await pg.evaluate(id => {
      document.querySelectorAll('.pview').forEach(v => v.classList.remove('active'));
      document.getElementById(id).classList.add('active');
    }, id);
    await (await pg.$('#' + id)).screenshot({ path: out });
  } else {
    await pg.screenshot({ path: out });
  }
  await b.close();
})();
