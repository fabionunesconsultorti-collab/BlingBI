# 🚀 Guia de Implantação e Publicação em Nuvem - BlingBI

Este guia ensina o passo a passo completo para publicar o **BlingBI** na nuvem de forma **gratuita**, permitindo acessar seu painel analítico de qualquer lugar e receber dados do **Bling ERP** em tempo real via Webhook HTTPS sem precisar de túneis temporários (como Ngrok).

---

## 📌 Por que o BlingBI não roda diretamente no GitHub Pages?

O **GitHub Pages** é uma hospedagem de **arquivos estáticos** (HTML, CSS e JavaScript puros). Como o BlingBI é uma aplicação completa com:
- Servidor **Python / Flask**;
- Banco de dados relacional (**SQLite / SQLAlchemy**);
- Sincronização em segundo plano com a API v3 do Bling;
- Geração dinâmica de relatórios em Excel e PDF;
- Recepção de Webhooks seguros com assinatura digital;

Ele necessita de um servidor com ambiente de execução (runtime). Para isso, plataformas modernas como **Render.com** e **Railway** oferecem planos gratuitos excelentes para executar aplicações Flask completas.

---

## 🌟 Opção 1: Publicação Gratuita no Render.com (Recomendado)

O [Render](https://render.com/) oferece hospedagem gratuita para Web Services com certificado SSL/HTTPS automático e deploy contínuo integrado ao GitHub.

### Passo 1: Suba seu repositório no GitHub
Se o seu projeto ainda não estiver no GitHub:
```bash
git add .
git commit -m "feat: suporte a deploy em nuvem com gunicorn e render"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/BlingBI.git
git push -u origin main
```

---

### Passo 2: Conecte o Render ao seu GitHub
1. Acesse **[dashboard.render.com](https://dashboard.render.com/)** e faça login (pode usar sua conta do GitHub).
2. Clique no botão **New +** no topo direito e selecione **Web Service**.
3. Escolha **"Build and deploy from a Git repository"** e clique em **Next**.
4. Conecte sua conta do GitHub e selecione o repositório **BlingBI**.

---

### Passo 3: Configure o Web Service
Preencha os campos conforme abaixo:

| Campo | Valor Recomendado |
|---|---|
| **Name** | `bling-bi` (ou o nome que preferir) |
| **Region** | `Oregon (US West)` ou `Ohio (US East)` |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn wsgi:app` |
| **Instance Type** | `Free` ($0/mês) |

---

### Passo 4: Configure as Variáveis de Ambiente (Environment Variables)
Ainda na tela de configuração (ou na aba **Environment** do serviço):
1. **`PYTHON_VERSION`**: `3.12.3`
2. **`FLASK_ENV`**: `production`
3. **`SECRET_KEY`**: Clique em *Generate* para gerar uma chave aleatória segura.
4. **`ADMIN_DEFAULT_PASSWORD`**: Defina uma senha forte e secreta para o Super Administrador geral (ou deixe o Render gerar um valor seguro).
5. **`CLEAR_DATABASE_PASSWORD`**: *(Opcional)* Defina uma senha de segurança para operações de limpeza/carga de dados.

### 🔑 Primeiro Acesso e Painel do Administrador Geral:
Ao concluir o deploy e acessar a URL da sua aplicação no Render:
- Acesse a tela de login: `https://sua-url.onrender.com/login`
- **Usuário:** `admgeral`
- **Senha:** A senha secreta que você configurou na variável de ambiente `ADMIN_DEFAULT_PASSWORD`
- No painel administrativo (`/admin`), você pode:
  1. Alterar a senha do administrador a qualquer momento.
  2. Cadastrar novos clientes com suas respectivas bases de dados dedicadas.
  3. Criar ou personalizar os segmentos de negócio, escolhendo quais telas e relatórios cada segmento terá acesso.
  4. Auditar qualquer cliente em tempo real via botão *"Acessar como Empresa"*.


*(Opcional)* Se desejar pré-configurar o Bling via ambiente em vez de preencher na tela:
- `BLING_CLIENT_ID`: Seu Client ID do aplicativo Bling
- `BLING_CLIENT_SECRET`: Seu Client Secret do aplicativo Bling

---

### Passo 5: Iniciar o Deploy
1. Clique em **Create Web Service**.
2. O Render clonará o repositório, instalará as dependências do `requirements.txt` e iniciará o Gunicorn.
3. Em cerca de 2 minutos, o status mudará para **Live** e você receberá uma URL pública como:
   👉 **`https://bling-bi.onrender.com`**

> [!NOTE]
> No plano gratuito do Render, a aplicação entra em modo de suspensão após 15 minutos sem visitas. Na primeira visita seguinte, ela pode demorar cerca de 30 a 50 segundos para acordar.

---

## 🔗 Adeus Ngrok! Como Configurar o Webhook no Bling ERP

Como a sua URL do Render já possui **HTTPS nativo e fixo**, você **não precisa mais rodar o Ngrok** no seu computador!

1. Acesse sua conta no **[Bling ERP](https://www.bling.com.br/)**.
2. Vá em **Preferências (engrenagem) > Notificações > Notificações/Webhooks**.
3. Crie um novo Webhook para os módulos desejados (ex: Pedidos de Venda, Contas a Receber).
4. No campo **URL de Envio**, insira a URL da sua aplicação no Render seguida de `/integrations/webhook`:
   ```
   https://seu-app.onrender.com/integrations/webhook
   ```
5. Salve a configuração. Pronto! Toda alteração no Bling atualizará seu painel de BI automaticamente na nuvem.

---

## 🗄️ Persistência do Banco de Dados

### Opção A: SQLite Padrão (Sem custos)
Por padrão, o BlingBI criará o banco `data/bling_bi.db`. 
- No Render gratuito, o sistema de arquivos é recriado a cada novo deploy. Se o banco reiniciar, o BlingBI **recarrega automaticamente os dados de demonstração ou puxa novamente da API do Bling**.

### Opção B: PostgreSQL Gratuito (Persistência 100% Permanente)
Para nunca perder os dados sincronizados mesmo após novos deploys:
1. No Render, clique em **New +** > **PostgreSQL**.
2. Escolha o plano **Free** e clique em **Create Database**.
3. Copie o valor de **Internal Database URL**.
4. Vá no seu Web Service do BlingBI, em **Environment**, e adicione a variável:
   - **`DATABASE_URL`**: `sua-url-do-postgres-copiada`
5. O BlingBI detectará o PostgreSQL automaticamente e criará todas as tabelas na inicialização!

---

## 🚂 Opção 2: Deploy no Railway.app

1. Crie uma conta no **[Railway.app](https://railway.app/)**.
2. Clique em **New Project** > **Deploy from GitHub repo**.
3. Selecione o repositório **BlingBI**.
4. O Railway detectará automaticamente o arquivo `Procfile` ou `Dockerfile` incluído no projeto e fará o deploy automático.

---

## 🐳 Opção 3: Executar via Docker Local ou VPS

Se preferir rodar em um servidor VPS próprio (DigitalOcean, Hetzner, AWS, etc.):

```bash
# 1. Construir a imagem Docker
docker build -t bling-bi .

# 2. Executar o container na porta 5000 com persistência do banco
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --name bling_bi_app \
  bling-bi
```
Acesse em: `http://localhost:5000` ou no IP público do seu servidor.
