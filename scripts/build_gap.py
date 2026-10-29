#!/usr/bin/env python3
"""Gera a página do Gap de Resultado (HTML único) a partir do dados.json.

Uso: python3 build_gap.py dados.json pasta-de-deploy/index.html
"""
import base64, datetime as dt, html, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(AQUI, '..', 'assets')
E = html.escape


def br(x, casas=0):
    s = f'{x:,.{casas}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def brl(x):
    if x is None:
        return '—'
    if abs(x) >= 10000:
        return f'R$ {br(x / 1000, 1)} mil' if abs(x) < 100000 else f'R$ {br(x / 1000)} mil'
    return f'R$ {br(x)}'


def qtd(x):
    return '—' if x is None else br(x)


def val(e, x):
    return brl(x) if e['dinheiro'] else qtd(x)


def cor(p):
    if p is None:
        return 'na'
    return 'ok' if p >= 1 else 'warn' if p >= 0.7 else 'bad'


def pctf(p):
    return f'{p * 100:.0f}%'


def ddmm(iso):
    d = dt.date.fromisoformat(iso)
    return f'{d:%d/%m}'


def meta_txt(m):
    if not m:
        return '—'
    if m['tipo'] == 'Faturamento':
        return f'Faturamento {brl(m["meta"]) if m["meta"] < 10000 else "R$ " + br(m["meta"])}'
    return f'{m["tipo"].capitalize()}: {qtd(m["meta"])}'


def pill_hs(hs):
    return f'<span class="pill {"bad" if hs is not None and hs < 21 else "neutral"}">HS {br(hs, 1).rstrip("0").rstrip(",") if hs is not None else "—"}</span>'


def pill_res(r):
    c = 'na' if r is None else 'bad' if r <= 3 else 'warn' if r < 7 else 'ok'
    return f'<span class="pill {c}">Resultado {qtd(r)}</span>'


def funil(p, corte):
    gk = p['gargalo']['etapa']
    out = (f'<div><h4>Realizado × esperado até {corte}</h4><div class="funnel"><div class="fscale"><span></span>'
           f'<span>0%</span><span class="m100">100% = esperado até {corte}</span><span>150%</span><span></span></div>')
    for e in p['etapas']:
        gap = e['k'] == gk
        c = cor(e['pct'])
        w = 0 if e['pct'] is None else min(e['pct'], 1.5) / 1.5 * 100
        flag = ' <span class="flag">gargalo</span>' if gap else ''
        out += (f'<div class="frow{" gap" if gap else ""}">\n  <div class="flabel">{e["rotulo"]}{flag}</div>\n'
                f'  <div class="ftrack"><div class="fexp"></div><div class="ffill {c}" style="width:{w:.1f}%"></div>'
                f'<span class="fpct">{"a lançar" if e["real"] is None else pctf(e["pct"])}</span></div>\n'
                f'  <div class="fnum"><b>{val(e, e["real"])}</b> de {val(e, e["esperado"])}'
                f'<span>meta do mês {val(e, e["meta"])}</span></div>\n</div>')
    return out + '</div></div>'


def conv(p):
    if not p['conversoes'] and not p['pendencias']:
        return '<div></div>'
    out = '<div>'
    if p['conversoes']:
        out += ('<div class="conv"><h4>Conversões: plano × realizado</h4><table><thead><tr><th></th>'
                '<th class="n">Plano</th><th class="n">Realizado</th></tr></thead><tbody>')
        for c in p['conversoes']:
            def fmt(x):
                if x is None:
                    return '—'
                return pctf(x) if c['tipo'] == 'pct' else f'R$ {br(x, 2)}' if c['tipo'] == 'brl' else f'{br(x, 1)}×'
            if c['real'] is None or not c['plano']:
                k = 'na'
            else:
                r = c['plano'] / c['real'] if c.get('menor_melhor') and c['real'] else c['real'] / c['plano']
                k = cor(r)
            out += f'<tr><td>{c["rotulo"]}</td><td class="n">{fmt(c["plano"])}</td><td class="n {k}">{fmt(c["real"])}</td></tr>'
        out += '</tbody></table></div>'
    if p['pendencias']:
        out += '<div class="pend"><h4>Pendências de dado</h4><ul>' + ''.join(f'<li>{E(x)}</li>' for x in p['pendencias']) + '</ul></div>'
    return out + '</div>'


def dimensoes(p, semanas):
    if not p.get('dimensoes'):
        if p.get('sem_cockpit'):
            return '<div class="dims"><h4>Dimensões</h4><p class="note">Projeto fora do Cockpit: sem dimensões nem histórico.</p></div>'
        return ''
    out = '<div class="dims"><h4>Dimensões</h4><div class="dgrid">'
    for d in p['dimensoes']:
        out += (f'<div class="dcol {"ok" if d["ok"] else "bad"}"><div class="dl">{d["rotulo"]}</div>'
                f'<div class="dv">{"✅" if d["ok"] else E(d["texto"])}</div></div>')
    out += ('</div><p class="note">Quem está certa leva ✅. Prazo falso traz a anomalia do Cockpit (tipo e motivo). '
            'Operação de tráfego falsa traz o motivo lançado na gestão de tráfego.</p></div>')
    hist = p.get('historico') or {}
    if semanas and any(any(v is not None for v in l) for l in hist.values()):
        ws = [ddmm(s) for s in semanas]
        out += f'<div class="dhist"><h5>Últimas {len(ws)} semanas</h5><div class="dht">'
        out += '<div class="dhr dhh"><span></span>' + ''.join(f'<span>{w[:2]}<i>{w[2:]}</i></span>' for w in ws) + '<span>ok</span></div>'
        for d in p['dimensoes']:
            linha = hist.get(d['rotulo'], [None] * len(ws))
            cells = ''
            for i, v in enumerate(linha):
                c = 'ok' if v is True else 'bad' if v is False else 'na'
                sym = '✓' if v is True else '✗' if v is False else '·'
                tip = f'{d["rotulo"]} em {ws[i]}: ' + ('marcada' if v is True else 'falsa' if v is False else 'sem registro')
                cells += f'<span class="dc {c}{" cur" if i == len(linha) - 1 else ""}" title="{tip}">{sym}</span>'
            cells += f'<span class="dcount">{sum(1 for v in linha if v is True)}/{sum(1 for v in linha if v is not None)}</span>'
            out += f'<div class="dhr"><span class="dhl">{d["rotulo"]}</span>{cells}</div>'
        out += (f'</div><p class="note">Fechamento de cada sábado no histórico do Cockpit; {ws[-1]} é a situação mais recente. '
                'Resultado conta como ✓ com nota 7 ou mais.</p></div>')
    return out


def plano(p):
    out = '<div class="plan"><h4>Plano de ação 5W1H</h4>'
    if not p.get('plano'):
        return out + '<div class="slot-box">Aguardando o plano de ação deste projeto.</div></div>'
    if p.get('plano_nota'):
        out += f'<p class="note">{E(p["plano_nota"])}</p>'
    for i, a in enumerate(p['plano'], 1):
        out += f'<div class="acard"><div class="ahead"><span class="anum">{i:02d}</span><span class="atitle">{E(a["titulo"])}</span></div><div class="w5">'
        for k, rot in (('porque', 'Por quê'), ('onde', 'Onde'), ('quando', 'Quando'), ('quem', 'Quem'), ('como', 'Como')):
            v = a.get(k) or 'a definir'
            out += f'<div class="w"><div class="wl">{rot}</div><div class="wv{" slot" if v == "a definir" else ""}">{E(v)}</div></div>'
        out += '</div></div>'
    return out + '</div>'


def card(p, d, ativo):
    fam = d['familias'][p['gargalo']['familia']][0]
    sec = f' <span class="g2">{E(p["gargalo"]["secundario"])}</span>' if p['gargalo'].get('secundario') else ''
    sobrancelha = p.get('sobrancelha') or ('HS abaixo de 21' if p['grupo'] == 'hs' else 'Resultado abaixo de 7')
    pills = pill_hs(p['hs']) + pill_res(p['resultado']) if not p.get('sem_cockpit') else ''
    if p.get('meta_oficial'):
        pills += f'<span class="pill neutral">Meta oficial: {meta_txt(p["meta_oficial"])}</span>'
    pills += ''.join(f'<span class="pill neutral">{E(x)}</span>' for x in p.get('pills_extra', []))
    corte = ddmm(d['corte'])
    pg = f'  <div class="pgrid">\n    {funil(p, corte)}\n    {conv(p)}\n  </div>\n' if p.get('etapas') else ''
    return (f'<article class="pview{" active" if ativo else ""}" id="pv-{p["id"]}">\n  <header class="phead">\n'
            f'    <div><div class="eyebrow">{E(sobrancelha)}</div><h3>{E(p["nome"])}</h3></div>\n'
            f'    <div class="ppills">{pills}</div>\n  </header>\n'
            f'  <div class="gbox {p["gargalo"]["familia"]}"><div class="gk">Gargalo</div><div class="gv">{fam}{sec}</div><p>{E(p["texto"])}</p></div>\n'
            f'{pg}  {dimensoes(p, d.get("semanas_historico"))}\n  {plano(p)}\n'
            f'  <p class="note">Fonte: {E(p.get("fonte") or d["fonte"])}</p>\n</article>')


def heat_row(p):
    gk = p['gargalo']['etapa']
    E_ = {e['k']: e for e in p.get('etapas', [])}
    out = (f'<tr data-grupo="{p["grupo"]}" data-proj="{p["id"]}"><th scope="row"><button class="rowlink" data-go="{p["id"]}">{E(p["nome"])}</button>'
           f'<div class="rowmeta">{pill_hs(p["hs"]) + pill_res(p["resultado"]) if not p.get("sem_cockpit") else ""}</div></th>')
    for k in ('inv', 'leads', 'mql', 'sql', 'vendas', 'fat'):
        e = E_.get(k)
        if not e:
            out += '<td class="hc na"><span class="hp">·</span></td>'
            continue
        gap = ' gap' if k == gk else ''
        tit = f'{e["rotulo"]}: {val(e, e["real"])} de {val(e, e["esperado"])} esperados'
        hp = 'a lançar' if e['real'] is None else pctf(e['pct'])
        out += f'<td class="hc {cor(e["pct"])}{gap}" title="{tit}"><span class="hp">{hp}</span><span class="hr">{val(e, e["real"])}</span></td>'
    m = p.get('meta_oficial')
    if m:
        out += f'<td class="hc {cor(m["pct"])}"><span class="hp">{pctf(m["pct"]) if m["pct"] is not None else "—"}</span><span class="hr">{meta_txt(m)}</span></td>'
    else:
        out += '<td class="hc na"><span class="hp">·</span></td>'
    f = p['gargalo']['familia']
    return out + f'<td class="gcell"><span class="gtag {f}">{FAM_NOMES[f]}</span></td></tr>'


FAM_NOMES = {}


def main():
    d = json.load(open(sys.argv[1]))
    saida = sys.argv[2]
    FAM_NOMES.update({k: v[0] for k, v in d['familias'].items()})
    P = d['projetos']
    css = open(os.path.join(ASSETS, 'style.css'), encoding='utf-8').read()
    logo = base64.b64encode(open(os.path.join(ASSETS, 'logo-v4.png'), 'rb').read()).decode()
    corte = dt.date.fromisoformat(d['corte'])
    ini = dt.date.fromisoformat(d['inicio_semana'])
    n_hs = sum(1 for p in P if p['grupo'] == 'hs')
    n_res = sum(1 for p in P if p['grupo'] == 'res')
    fora = d.get('fora', [])
    total = len(P) + len(fora)
    com_plano = sum(1 for p in P if p.get('plano'))
    h = [f'<!doctype html>\n<html lang="pt-BR" data-theme="light"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
         f'<title>Gap de Resultado S{d["semana"]}</title><style>\n{css}</style></head>\n<body>',
         f'<header class="top"><div><img class="brandmark" src="data:image/png;base64,{logo}" alt="V4 Company">Quality Check · <b>{E(d["coordenador"])}</b>{" → " + E(d["revisor"]) if d.get("revisor") else ""}</div>',
         f'<div class="meta">Semana {d["semana"]}/{d["ano"]} ({ini:%d}–{corte:%d/%m}) · pacing até {corte:%d/%m}</div></header>\n<main>',
         f'<div class="eyebrow">Gap de Resultado · S{d["semana"]}</div>',
         '<h1>Onde o funil quebra nos projetos com HS abaixo de 21 ou Resultado abaixo de 7</h1>',
         f'<p class="lede">Cada etapa compara o realizado com o esperado até {corte:%d/%m}: meta do mês × {corte.day}/{d["dias_mes"]} dias '
         f'({corte.day / d["dias_mes"] * 100:.0f}% do mês).\nMetas e realizado da aba Gestão de Tráfego do Cockpit; HS e Resultado do Cockpit.</p>',
         '<div class="kpis">',
         f' <div class="kpi"><div class="eyebrow">No recorte</div><div class="v">{len(P)} de {total}</div><div class="s">projetos da carteira</div></div>',
         f' <div class="kpi"><div class="eyebrow">HS abaixo de 21</div><div class="v">{n_hs}</div><div class="s">entram pelo Health Score</div></div>',
         f' <div class="kpi"><div class="eyebrow">Resultado abaixo de 7</div><div class="v">{n_res}</div><div class="s">com HS ≥ 21</div></div>',
         f' <div class="kpi"><div class="eyebrow">Fora do recorte</div><div class="v">{len(fora)}</div><div class="s">{E(", ".join(f["nome"] for f in fora)) or "—"}</div></div>',
         '</div>', '<h2>Onde está o gargalo</h2>', '<p class="note">Clique no projeto para abrir o funil dele.</p>', '<div class="fams">']
    for k, (nome, desc) in d['familias'].items():
        ps = [p for p in P if p['gargalo']['familia'] == k]
        chips = ''.join(f'<button class=chip data-go={p["id"]}>{E(p["nome"])}</button>' for p in ps)
        h.append(f'<div class="fam {k}"><div class="famh"><span class="famn">{len(ps)}</span><div><b>{nome}</b><span>{desc}</span></div></div><div class="famlist">{chips}</div></div>')
    h += ['</div>', f'<h2>Mapa do funil: realizado ÷ esperado até {corte:%d/%m}</h2>', '<div class="filters">',
          f' <button class="active" data-f="all">Todos ({len(P)})</button><button data-f="hs">HS &lt; 21 ({n_hs})</button><button data-f="res">Resultado &lt; 7 ({n_res})</button>',
          ' <div class="legend"><span><i style="background:var(--ok-bg);border:1px solid var(--ok)"></i>no ritmo (≥100%)</span>',
          ' <span><i style="background:var(--warn-bg);border:1px solid var(--warn)"></i>70–99%</span><span><i style="background:var(--bad-bg);border:1px solid var(--bad)"></i>abaixo de 70%</span>',
          ' <span><i style="background:var(--na-bg)"></i>sem meta / não lançado</span></div>', '</div>',
          '<div class="heatwrap"><table class="heat"><thead><tr><th>Projeto</th><th>Invest.</th><th>Leads</th><th>MQL</th><th>SQL</th><th>Vendas</th><th>Fatur.</th><th>Meta oficial</th><th>Gargalo</th></tr></thead><tbody>']
    for g, rot in (('hs', 'HS abaixo de 21'), ('res', 'Resultado abaixo de 7 com HS ≥ 21')):
        ps = [p for p in P if p['grupo'] == g]
        if ps:
            h.append(f'<tr class="grp" data-grupo="{g}"><td colspan="9">{rot} · {len(ps)} projeto{"s" if len(ps) > 1 else ""}</td></tr>')
            h += [heat_row(p) for p in ps]
    h += ['</tbody></table></div>', '<h2 id="detalhe">Por projeto</h2>',
          f'<p class="note">{com_plano} de {len(P)} com plano de ação 5W1H.</p>',
          '<div class="switch">' + ''.join(f'<button class="{"active" if i == 0 else ""}" data-go="{p["id"]}">{E(p["nome"])}</button>' for i, p in enumerate(P)) + '</div>']
    h += [card(p, d, i == 0) for i, p in enumerate(P)]
    h += ['</main>', f'<footer>{E(d.get("rodape") or "Cockpit (Health Score, Resultado, aba Gestão de Tráfego e histórico das dimensões) · gap-de-resultado")}</footer>',
          """<script>
function go(t){document.querySelectorAll('.switch button').forEach(b=>b.classList.toggle('active',b.dataset.go===t));
document.querySelectorAll('.pview').forEach(v=>v.classList.toggle('active',v.id==='pv-'+t));
document.getElementById('detalhe').scrollIntoView({behavior:'smooth',block:'start'});}
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go)));
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{
document.querySelectorAll('.filters button').forEach(x=>x.classList.toggle('active',x===b));
const f=b.dataset.f;document.querySelectorAll('.heat tbody tr').forEach(r=>{r.style.display=(f==='all'||r.dataset.grupo===f)?'':'none';});}));
</script>
</body></html>"""]
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    open(saida, 'w', encoding='utf-8').write('\n'.join(h))
    print(f'{len(P)} projetos, {com_plano} com plano -> {saida}')


if __name__ == '__main__':
    main()
