# GELA — Fase 1

Sistema pessoal para busca, triagem e exportação de literatura científica, sem uso de IA generativa sobre os dados dos artigos.

## O que está pronto e testado

- Login por senha única
- Busca booleana (AND/OR) combinando **OpenAlex** (funcional e testado contra a documentação oficial)
- Deduplicação por DOI entre fontes
- Triagem (relevante / descartar, com motivo de exclusão)
- Banco Postgres (Supabase), acessado via `psycopg2`
- Exportação: relatório estilo PRISMA (.md), pacote para Obsidian (.zip com notas interligadas), consolidado para NotebookLM (.md)

## O que está pendente ou não verificado — leiam antes de confiar nos resultados

- **SciELO**: o cliente (`clients/scielo.py`) foi escrito com base em um endpoint que **não encontrei confirmado na documentação oficial da SciELO** — só numa listagem de terceiros. Testem com uma busca real antes de confiar nos números. Se o formato de resposta for diferente do esperado, o sistema vai mostrar um erro claro em vez de dados errados.
- **PhilPapers**: **não implementado**. A documentação oficial deles pede contato prévio com a equipe antes de qualquer aplicação automatizada usar a API, e não encontrei a sintaxe de busca documentada publicamente. Ver instruções detalhadas em `clients/philpapers.py`.

## Como rodar

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
2. Copie `.env.example` para `.env` e preencha:
   - `DATABASE_URL`: connection string do Postgres/Supabase (Project Settings -> Database -> Connection string -> URI)
   - `GELA_PASSWORD`: a senha que vocês vão usar para entrar
   - `FLASK_SECRET_KEY`: qualquer string aleatória longa
   - `OPENALEX_API_KEY`: crie gratuitamente em https://openalex.org (sem isso, o limite diário de busca é de só 100 requisições)
3. Crie as tabelas (só precisa rodar uma vez, ou quando o schema mudar):
   ```
   python3 init_db.py
   ```
4. Rode:
   ```
   python3 app.py
   ```
5. Acesse http://localhost:5000

## Testando a lógica sem depender das APIs externas

`DATABASE_URL=postgresql://... python3 test_logica_interna.py` roda um conjunto de testes com dados simulados (claramente marcados como simulados) contra um schema Postgres isolado (`gela_test`, criado e apagado pelo próprio script), validando banco de dados, deduplicação e exportação sem precisar de conexão com OpenAlex/SciELO.

## Deploy no Vercel

- O projeto já inclui `vercel.json` configurando `app.py` como função serverless Python (runtime WSGI).
- Configure as variáveis de ambiente no painel do Vercel (Project Settings -> Environment Variables): `DATABASE_URL`, `GELA_PASSWORD`, `FLASK_SECRET_KEY`, `OPENALEX_API_KEY`, `OPENALEX_EMAIL`.
- Rode `python3 init_db.py` localmente (apontando para o mesmo `DATABASE_URL` de produção) para criar as tabelas antes do primeiro acesso — o app não cria tabelas sozinho a cada cold start.

## Próximos passos sugeridos (Fase 2, não construída ainda)

- Resolver e validar a integração com SciELO
- Formalizar a integração com PhilPapers (após contato com a equipe deles)
- Busca semântica como modo exploratório opcional, sempre separado da busca booleana documentada
