# ⚽ Football Career Legacy

Aplicação web de modo carreira de futebol, com frontend em HTML, CSS e JavaScript e API REST em Python, com dois estilos de jogo: **modo técnico** e **modo jogador**. O projeto foi desenvolvido para fins acadêmicos e utiliza Python, FastAPI e SQLite. Pode ser executado localmente ou hospedado em uma VM Linux no Microsoft Azure.

## Visão geral

- **Modo técnico (`MANAGER`):** escolha um clube, defina formação e tática, gerencie titulares, contrate e venda jogadores, acompanhe o orçamento e a confiança da diretoria.
- **Modo jogador (`PLAYER`):** crie seu atleta, dispute temporadas, evolua o rating, consulte estatísticas e receba propostas de outros clubes.
- Cada carreira cria um mundo independente, identificado por `career_id`.
- Cada mundo contém oito clubes fictícios, elencos iniciais de 18 jogadores por clube, dez agentes livres e um campeonato de turno e returno com 14 rodadas.
- As partidas são simuladas com base na força ofensiva e defensiva, formação, tática, rating dos atletas e mando de campo.

## Tecnologias

| Tecnologia | Uso |
|---|---|
| Python 3.10+ | Linguagem da aplicação e regras do jogo |
| FastAPI | API REST e documentação OpenAPI/Swagger |
| Pydantic | Validação dos dados de entrada |
| SQLite (`sqlite3`) | Persistência dos dados em `data/career.db` |
| Uvicorn | Servidor ASGI da aplicação |
| Nginx | Proxy reverso na VM Linux |
| systemd | Inicialização e supervisão do serviço |
| pytest + httpx | Testes automatizados |

## Interface web

O frontend está em `frontend/` e consome a API na mesma origem (`const API = ""`). O backend não publica arquivos estáticos: o servidor web deve servir o frontend e encaminhar as rotas da API para o Uvicorn.

### Funções disponíveis

| Área | Interface web |
|---|---|
| Carreiras | Criar técnico ou jogador, listar e continuar carreiras salvas |
| Jogo | Simular uma rodada com confirmação e iniciar a próxima temporada |
| Liga | Classificação com destaque do clube e calendário da equipe com placares |
| Técnico | Orçamento, confiança, formação, tática, campo e cards por posição |
| Escalação | Escolher titulares nos cards, conferir limites por posição e salvar |
| Jogador | Perfil, overall, potencial, idade, clube e valor de mercado |
| Estatísticas | Jogos, gols, assistências e nota média da temporada e da carreira |
| Histórico | Desempenho do jogador por temporada |
| Transferências do jogador | Estado da janela, propostas, papel no elenco, força e última classificação do clube; aceitação com confirmação |

Os totais incluem a temporada atual. A nota média de carreira é calculada no frontend ponderando as médias por quantidade de jogos; pode apresentar pequenas diferenças de arredondamento porque a API já arredonda as médias de cada temporada. Antes da primeira partida, a nota aparece como “—”.

As propostas são geradas na transição para uma nova temporada; uma janela aberta não garante ofertas. O botão de aceitar exige carreira ativa, janela aberta e proposta pendente. A aceitação muda o clube e recusa as demais propostas pendentes. A interface atualiza perfil, classificação e calendário após a transferência.

O mercado de compra e venda do técnico, a artilharia, a consulta detalhada de outros clubes, a exclusão de carreiras e a aposentadoria manual estão disponíveis pela API, sem tela dedicada no frontend atual.

### Como jogar

1. Em **Nova carreira**, escolha técnico ou jogador e preencha os dados.
2. No modo técnico, escolha uma formação e uma tática. Para trocar um titular, retire primeiro um atleta da mesma posição e selecione o reserva desejado.
3. Confira os **11 titulares** e os limites de posições; use **Salvar escalação e tática** para persistir. A escalação automática prepara a seleção, mas também precisa ser salva.
4. Simule as rodadas e acompanhe classificação e calendário.
5. Após a rodada 14, use **Iniciar próxima temporada**.
6. No modo jogador, consulte perfil e propostas. Aceite uma oferta somente após revisar o clube e o papel no elenco na confirmação.

## Regras do jogo

### Estrutura das carreiras

- Oito clubes: Tigres do ABC, Leões Paulistas, Águias do Sul, Tubarões FC, Dragões United, Falcões da Serra, Lobos do Cerrado e Fênix Carioca.
- Cada clube começa com 18 jogadores: 2 goleiros, 6 defensores, 6 meio-campistas e 4 atacantes.
- Dez jogadores livres ficam disponíveis no mercado.
- Posições: `GK`, `DEF`, `MID` e `ATT`.
- Formações: `4-4-2`, `4-3-3` e `3-5-2`.
- Táticas: `BALANCED`, `ATTACK` e `DEFENSE`.
- Cada temporada tem 14 rodadas. A janela de transferências abre antes da rodada 1 e antes da rodada 8.

### Simulação de partidas

A API calcula a força ofensiva e defensiva a partir dos 11 titulares, suas posições e ratings. A tática escolhida aplica modificadores sobre o ataque ou a defesa, e o time mandante recebe uma vantagem. A quantidade de gols é simulada por uma distribuição de Poisson. Autores de gols e assistências são sorteados com pesos por posição e rating, e os titulares recebem uma nota pela atuação.

### Modo técnico

A confiança da diretoria começa em 60 pontos: vitória acrescenta 4, derrota retira 4 e empate não altera o valor. Ao fim da temporada, a confiança é ajustada conforme a posição final e a meta esportiva. O técnico é demitido quando a confiança chega a **15 ou menos**.

O orçamento inicial é de 30 milhões. O valor recebido ao final de cada temporada varia conforme a classificação. Compras e vendas só podem ser realizadas durante a janela de transferências.

A escalação deve ter 11 atletas e respeitar a formação selecionada. A API também impede que uma transferência reduza o elenco abaixo do mínimo de 16 jogadores ou retire a cobertura posicional necessária: pelo menos 1 GK, 4 DEF, 5 MID e 3 ATT.

**Regras de preço do mercado:** a contratação de um agente livre custa 90% do valor-base; a compra de um jogador vinculado a outro clube custa 120%; a venda de um jogador rende 70%. Essa diferença evita lucro artificial em uma compra seguida de revenda imediata.

### Modo jogador

O atleta é criado com idade entre 16 e 21 anos e começa no clube de menor força. Ao fim de cada temporada, seu rating pode evoluir ou cair de acordo com a idade e o desempenho. A API registra jogos, gols, assistências, nota média e histórico por temporada. Podem ser geradas até três propostas de outros clubes, que o jogador pode aceitar durante a janela de transferências. A aposentadoria automática ocorre aos 36 anos; também é possível encerrar a carreira manualmente.

## Endpoints

A documentação interativa fica disponível em `/docs`, e o esquema OpenAPI pode ser consultado em `/openapi.json`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Verifica se a API está disponível |
| GET | `/clubs` | Lista os clubes disponíveis |
| POST | `/careers` | Cria uma carreira `MANAGER` ou `PLAYER` |
| GET | `/careers` | Lista as carreiras |
| GET | `/careers/{cid}` | Retorna o resumo de uma carreira |
| DELETE | `/careers/{cid}` | Exclui uma carreira e seus dados relacionados |
| GET | `/careers/{cid}/standings` | Consulta a classificação |
| GET | `/careers/{cid}/fixtures` | Consulta calendário e resultados |
| GET | `/careers/{cid}/teams` | Lista os clubes da carreira |
| GET | `/careers/{cid}/teams/{team_id}` | Consulta um clube e seu elenco |
| GET | `/careers/{cid}/top-scorers` | Consulta a artilharia e estatísticas |
| GET | `/careers/{cid}/squad` | Consulta o elenco do clube do usuário |
| POST | `/careers/{cid}/advance` | Simula uma ou mais rodadas |
| POST | `/careers/{cid}/next-season` | Encerra a temporada e inicia a próxima |
| PUT | `/careers/{cid}/lineup` | Técnico: define formação, tática e titulares |
| GET | `/careers/{cid}/market` | Técnico: consulta jogadores disponíveis |
| POST | `/careers/{cid}/market/buy` | Técnico: contrata um jogador |
| POST | `/careers/{cid}/market/sell` | Técnico: vende um jogador |
| GET | `/careers/{cid}/player` | Jogador: consulta ficha e histórico |
| GET | `/careers/{cid}/offers` | Jogador: consulta propostas recebidas |
| POST | `/careers/{cid}/offers/{offer_id}/accept` | Jogador: aceita uma proposta |
| POST | `/careers/{cid}/retire` | Jogador: encerra a carreira manualmente |

### Exemplos de entrada

Criar uma carreira de técnico:

```json
{
  "name": "Minha carreira",
  "mode": "MANAGER",
  "club": "Tigres do ABC"
}
```

Criar uma carreira de jogador:

```json
{
  "name": "Minha carreira como jogador",
  "mode": "PLAYER",
  "player": {
    "name": "Meu Atleta",
    "position": "ATT",
    "age": 18
  }
}
```

Configurar formação e tática:

```json
{
  "formation": "4-3-3",
  "tactic": "ATTACK"
}
```

O campo `starters` pode ser enviado opcionalmente como uma lista com exatamente 11 IDs de jogadores do próprio elenco, respeitando a formação escolhida. Quando omitido, a API monta a escalação automaticamente.

## Banco de dados SQLite

O banco fica por padrão em `data/career.db`. O caminho pode ser alterado pela variável de ambiente `DB_PATH`.

| Tabela | Conteúdo |
|---|---|
| `careers` | Nome, modo, status, temporada, rodada, clube/jogador controlado e confiança da diretoria |
| `teams` | Clubes da carreira, cidade, orçamento, formação e tática |
| `players` | Jogadores, posição, idade, rating, potencial e titularidade |
| `fixtures` | Calendário, rodada, mandante, visitante e placar |
| `goals` | Gols, autor, assistência e minuto |
| `season_stats` | Jogos, gols, assistências e notas por atleta/temporada |
| `offers` | Propostas de transferência e seus status |

As conexões ativam `PRAGMA foreign_keys = ON`. As consultas que recebem parâmetros da API utilizam placeholders SQL. O SQLite é adequado ao volume esperado para a demonstração acadêmica e não exige um serviço de banco de dados separado.

## Execução local

Requisitos: Python 3.10 ou superior.

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

pip install -r requirements.txt
uvicorn main:app --reload
```

Acesse `http://127.0.0.1:8000/docs`.

## Testes automatizados

Instale as dependências de desenvolvimento e execute:

```bash
pip install -r requirements-dev.txt
pytest -q
```

Os testes utilizam um banco temporário e cobrem a disponibilidade da API, o catálogo de clubes, o isolamento entre carreiras, a validação de escalação, as regras do mercado, a cobertura mínima do elenco, a progressão de temporada e a criação/verificação de backup SQLite.

## Backup e restauração do SQLite

O script `backup_db.py` utiliza a API de backup do próprio SQLite para criar uma cópia consistente, mesmo com a aplicação em execução. O arquivo gerado passa por `PRAGMA integrity_check`. Por padrão, backups com mais de 14 dias são removidos.

Execução manual:

```bash
DB_PATH=/opt/football-career-api/data/career.db \
BACKUP_DIR=/var/backups/football-api \
BACKUP_RETENTION_DAYS=14 \
python backup_db.py
```

Para restaurar, pare o serviço, mantenha uma cópia do banco atual e substitua o arquivo pelo backup validado:

```bash
sudo systemctl stop football-career-api
sudo cp /opt/football-career-api/data/career.db /opt/football-career-api/data/career.db.pre-restore
sudo cp /var/backups/football-api/career-AAAAmmddTHHMMSSZ.db /opt/football-career-api/data/career.db
sudo chown azureuser:azureuser /opt/football-career-api/data/career.db
sudo systemctl start football-career-api
```

Ajuste usuário, diretórios e nome do arquivo ao ambiente real. É recomendável testar a restauração antes de depender do backup.

## Ambiente registrado nas evidências

As capturas de 02/11/2026 registram a VM `vm-football-career` no grupo `rg-football-career`, região Canada Central, assinatura Azure for Students. Na criação foram selecionados Ubuntu Server 24.04 LTS x64 Gen2, Standard_B2ats_v2 (2 vCPUs e 1 GiB) e SSD Standard com imagem padrão de 30 GiB. O IP público registrado é `20.104.57.183`; sua disponibilidade atual não foi verificada nesta documentação.

O terminal mostra a instalação em `/opt/football-career-api`, serviço `football-career-api.service`, Python 3.12.3, FastAPI 0.115.6 e Uvicorn 0.32.1. Os prints incluem Swagger público, integridade do SQLite, backup criado e consulta a uma cópia restaurada. Não há captura de execução de pytest ou de agendamento por cron.

O relatório técnico resumido tem 15 páginas e 18 figuras selecionadas entre os prints recebidos. As imagens do frontend registram o layout anterior às melhorias finais; as telas de erro estão identificadas como etapas de diagnóstico. Dois recortes sem conteúdo legível foram excluídos.

## Implantação de referência no Azure (Ubuntu 24.04)

O roteiro abaixo serve como referência para a atividade. Os campos de Resource Group, região, SKU, IP e disco devem ser preenchidos com os valores reais apresentados no portal Azure. O README não comprova que o deploy já foi executado.

### 1. Recursos de nuvem

Registre ou crie os seguintes componentes:

- Resource Group;
- VM com Ubuntu Server 24.04 LTS e a SKU escolhida;
- OS Disk (tipo e capacidade);
- VNet e interface de rede (NIC);
- IP público;
- Network Security Group (NSG), liberando SSH (22) apenas para o IP administrativo e HTTP (80) para acesso à API.

Para esta demonstração, o acesso externo é realizado por HTTP. Não é necessário configurar domínio, certificado TLS ou HTTPS. A porta 8000 do Uvicorn deve permanecer acessível apenas localmente na VM; o Nginx recebe a conexão na porta 80 e encaminha a requisição para a aplicação.

### 2. Instalação e clonagem

```bash
ssh azureuser@<IP_PUBLICO>
sudo apt update
sudo apt install -y python3-venv nginx git

sudo mkdir -p /opt/football-career-api
sudo chown "$USER":"$USER" /opt/football-career-api
git clone --branch master https://github.com/kauasoares/football-career-api.git /opt/football-career-api
cd /opt/football-career-api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p data
```

### 3. Serviço systemd

Crie `/etc/systemd/system/football-career-api.service`:

```ini
[Unit]
Description=Football Career API
After=network.target

[Service]
User=azureuser
WorkingDirectory=/opt/football-career-api
Environment=DB_PATH=/opt/football-career-api/data/career.db
ExecStart=/opt/football-career-api/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Ative e valide:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now football-career-api
systemctl status football-career-api
```

### 4. Nginx para o frontend e a API

Crie `/etc/nginx/sites-available/football-api`:

```nginx
server {
    listen 80;
    server_name _;

    root /opt/football-career-api/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~ ^/(health|clubs|careers|docs|redoc|openapi\.json)(/|$) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ative o site e teste a configuração:

```bash
sudo ln -s /etc/nginx/sites-available/football-api /etc/nginx/sites-enabled/football-api
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

O bloco acima é uma configuração de referência, não uma alteração automática da VM. Ajuste o caminho `/opt/football-career-api` ao diretório realmente instalado, por exemplo `/opt/football-career-api`. O usuário do Nginx precisa conseguir ler o diretório `frontend/`. Não abra o HTML diretamente pelo protocolo `file://`: o frontend espera rotas HTTP da API na mesma origem.

### 5. Validação do frontend e da API

No navegador, Postman ou curl, utilize o IP público da VM:

```text
http://<IP_PUBLICO>/
http://<IP_PUBLICO>/health
http://<IP_PUBLICO>/docs
```

A rota `/health` deve retornar `{"status":"ok"}` e `/docs` deve abrir a documentação interativa do FastAPI.

### 6. Agendamento de backup (opcional)

```bash
sudo mkdir -p /var/backups/football-api
sudo chown azureuser:azureuser /var/backups/football-api
crontab -e
```

Adicione uma execução diária às 02h:

```cron
0 2 * * * DB_PATH=/opt/football-career-api/data/career.db BACKUP_DIR=/var/backups/football-api BACKUP_RETENTION_DAYS=14 /opt/football-career-api/.venv/bin/python /opt/football-career-api/backup_db.py >> /home/azureuser/football-api-backup.log 2>&1
```

## Atualização do frontend na instalação existente

Na pasta real do repositório na VM:

```bash
git pull origin master
```

Depois, recarregue o navegador com **Ctrl + F5**. Alterações somente nos arquivos estáticos não exigem reiniciar o backend quando o Nginx já serve diretamente a pasta `frontend/`.

Se aparecer `version is not defined` ao continuar uma carreira, confirme que a instalação inclui o commit `dde372b` ou posterior e recarregue os scripts sem cache. Essa correção inicializa o controle de versão do carregamento do dashboard.

## Documentação e evidências

A documentação técnica atualizada reúne arquitetura, contratos da API, manual dos modos técnico e jogador, configuração de referência, backup e evidências legendadas. A entrega revisada está disponível em [PDF](Football_Career_API_Documentacao_Tecnica.pdf). O arquivo Word existente no histórico do projeto é uma versão anterior e não integra esta revisão. Prints do ambiente devem ser apresentados com legenda e contexto, distinguindo a interface anterior da versão atual. Diagramas explicativos não substituem evidências de execução.

## Escopo acadêmico e observações

A API não implementa cadastro de usuários nem autenticação. As rotas ficam abertas para facilitar os testes do professor por Swagger, Postman ou curl. O acesso HTTP sem TLS é utilizado apenas para a demonstração acadêmica, conforme o escopo do projeto. Não envie dados pessoais, senhas ou informações sensíveis pela API.

Mesmo em um projeto acadêmico, recomenda-se restringir a porta SSH (22) ao IP administrativo e manter a porta 8000 do Uvicorn fechada para acesso externo. O NSG deve permitir a porta 80 para a demonstração e a porta 22 para administração.

## Limitações e melhorias futuras

- O frontend cobre os fluxos descritos acima; algumas operações continuam disponíveis somente pela API.
- SQLite é adequado para o escopo acadêmico, mas permite apenas uma escrita por vez e não foi projetado para escalar horizontalmente entre várias VMs.
- Não há autenticação de usuários ou autorização por carreira; qualquer pessoa com acesso à API pode executar as operações disponíveis.
- O ambiente demonstrativo utiliza HTTP, sem criptografia de transporte; HTTPS pode ser adicionado caso o projeto seja levado a um cenário público de produção.
- Não há pipeline CI/CD nem ferramenta de migração versionada do esquema do banco.

Evoluções possíveis: ampliar a interface do mercado do técnico, adicionar contas e permissões individuais, implementar logs e métricas, automatizar testes e publicação com GitHub Actions e migrar para PostgreSQL caso a concorrência e o volume de dados aumentem.

## Estrutura de arquivos

```text
football-career-api/
├── main.py
├── backup_db.py
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── .gitignore
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── style.css
│   │   ├── tactics.css
│   │   └── career.css
│   └── js/
│       ├── api.js
│       ├── tactics.js
│       └── player.js
└── tests/
    └── test_api.py
```
