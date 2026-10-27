# Incidentes públicos no Brasil

Mapa e catálogo de incidentes digitais no Brasil a partir de fontes abertas. Cada ponto é um caso publicado, não um ataque observado em tempo real.

## Plano

1. Ler alegações públicas de ransomware com país BR na base aberta do [Ransomware.live](https://www.ransomware.live/map/BR).
2. Ler RSS de veículos brasileiros, a janela recente de ataques citados na imprensa do [Ransomware.live](https://www.ransomware.live/cyberattacks) e o [GDELT](https://www.gdeltproject.org/), quando a API responde. Além de ransomware e vazamento, a manchete pode citar CVE, invasão em PHP ou webshell, desde que o caso seja no Brasil.
3. Classificar o título (ransomware, vazamento ou ataque) e descartar "invasão" que não é digital, como terra, campo ou casa.
4. Achar município ou UF no texto, com a malha de municípios do IBGE. A coordenada é a cidade citada ou o centro do estado.
5. Juntar notícias que citam a mesma organização e gravar só o que pode ir para o mapa: nome, data, setor, grupo citado, precisão e link da fonte.
6. Mostrar a lista, o filtro e o mapa. Caso sem lugar fica na lista e não vira ponto.
7. Guardar relatos públicos do Paraná que o RSS não arquiva, com cidade e link da notícia. O apagão da CrowdStrike em Paranaguá não entra, porque não foi um ataque.

Não entram URL de site `.onion`, inventário de arquivo vazado nem dado pessoal. A alegação de ransomware não é tratada como confirmação oficial.

## Atualizar o catálogo

O mapa lê o arquivo `web/data/catalog.json`. Ele não consulta uma API ao vivo. Para trazer casos novos de 2026, rode de novo:

```bash
python scripts/build_catalog.py
python -m http.server 8765 --directory web
```

O script baixa o JSON aberto do Ransomware.live, a página recente de ataques na imprensa, o RSS e, se a API responder, até 12 meses de manchetes do GDELT. Se o GDELT recusar, a coleta segue com o que já estiver em cache. O RSS e a página de imprensa não guardam o ano inteiro, só o que estiver publicado na hora da coleta.
