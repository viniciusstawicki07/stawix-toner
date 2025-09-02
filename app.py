from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, current_app
import ldap3
from config import get_db_connection
from functools import wraps
from flask_mail import Mail, Message
from threading import Thread
from flask_login import LoginManager, login_user, logout_user, login_required, current_user # NOVO
from models import User # NOVO

app = Flask(__name__)
app.secret_key = '1cd672b1fd06fe7c539aedc7913556edd47846cfa5ca237b'

# --- Configuração do Flask-Login --- (NOVO)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Configuração LDAP
LDAP_SERVER = 'ldap://10.101.2.2:389'
LDAP_BASE_DN = 'OU=BomJesus,DC=cooperativabomjesus,DC=Com,DC=Br'
LDAP_BIND_DN = "CN=Vinicius Muller,OU=Informatica,OU=Matriz,OU=Lapa,OU=Usuarios,OU=BomJesus,DC=cooperativabomjesus,DC=com,DC=br"
LDAP_BIND_PASSWORD = "Vms071999"
LDAP_USERNAME_ATTRIBUTE = "sAMAccountName"
LDAP_USER_SEARCH_FILTER = "(&(objectClass=user)(|(sAMAccountName=%s)(userPrincipalName=%s)))"
ADMIN_USERNAMES = ['carlos.hoffmann', 'bruno.marcondes', 'acyr.martins', 'claudiney.andrade', 'walmir.stanula', 'vinicius.muller']
EMAIL_ADMIN_GROUP = ['vinicius.muller@bj.coop.br']
OU_ENTREPOSTOS_SETORES = {
    "Antonio Olinto": {"entrepostos": [8, 21], "setores": [15]},
    "Balsa Nova": {"entrepostos": [10, 18], "setores": [15]},
    "Contenda": {"entrepostos": [4], "setores": [15]},
    "Irati": {"entrepostos": [12], "setores": [15]},
    "Mafra": {"entrepostos": [22], "setores": [15]},
    "Mallet": {"entrepostos": [17], "setores": [15]},
    "Palmeira": {"entrepostos": [11, 23, 25], "setores": [15]},
    "Paulo Frontin": {"entrepostos": [9, 16], "setores": [15]},
    "Quitandinha": {"entrepostos": [5, 13], "setores": [15]},
    "Rebouças": {"entrepostos": [15], "setores": [15]},
    "Sao Joao do Triunfo": {"entrepostos": [6, 20], "setores": [15]},
    "Sao Mateus do Sul": {"entrepostos": [7], "setores": [15]},
    "Boqueirão": {"entrepostos": [3], "setores": [11, 12, 13, 14]},
    "Capao Bonito": {"entrepostos": [14, 24], "setores": [15]},
    "Fabrica de Racao": {"entrepostos": [19], "setores": [15]},
    "Balanca": {"entrepostos": [1], "setores": [9]},  # Sede - Balanca
    "Comercial Cereais": {"entrepostos": [1], "setores": [6]},
    "Comercial Insumos": {"entrepostos": [1], "setores": [6]},
    "Contabilidade": {"entrepostos": [1], "setores": [4]},
    "DeTec": {"entrepostos": [1], "setores": [5]},
    "Financeiro": {"entrepostos": [1], "setores": [2]},
    "Informatica": {"entrepostos": [1], "setores": [1]},  # Apenas "01 - Sede"
    "Loja Insumos": {"entrepostos": [1], "setores": [8, 10]},
    "Recursos Humanos": {"entrepostos": [1], "setores": [3, 7]},
}

# Função de autenticação via LDAP
def authenticate(username, password):
    try:
        # ... (conexão LDAP inicial igual)
        server = ldap3.Server(LDAP_SERVER)
        conn = ldap3.Connection(server, LDAP_BIND_DN, LDAP_BIND_PASSWORD)
        if not conn.bind(): return None
        
        # MODIFICADO: Adicionado sAMAccountName aos atributos
        conn.search(LDAP_BASE_DN, f'(&(objectClass=user)(sAMAccountName={username}))', attributes=['displayName', 'mail', 'distinguishedName', 'sAMAccountName'])

        if not conn.entries: return None

        user_entry = conn.entries[0]
        user_dn = user_entry.distinguishedName.value
        
        # Tenta autenticar com as credenciais do usuário
        user_conn = ldap3.Connection(server, user_dn, password)
        if user_conn.bind():
            return {
                "username": user_entry.sAMAccountName.value,
                "full_name": user_entry.displayName.value,
                "email": user_entry.mail.value,
                "distinguished_name": user_dn
            }
        return None
    except Exception as e:
        print(f"Erro na autenticação LDAP: {str(e)}")
        return None

# Função de administrador obrigatório
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso restrito aos administradores.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_ou(distinguished_name):
    """
    Extrai a OU do distinguishedName do usuário com base nas regras específicas.
    """
    try:
        # Divida o DN em partes e filtre apenas as OUs
        ou_parts = [part.split('=')[1] for part in distinguished_name.split(',') if part.startswith('OU=')]

        # Regras específicas para determinar a OU
        if len(ou_parts) >= 3 and ou_parts[2] == "Entrepostos":
            return ou_parts[1]
        elif len(ou_parts) >= 3 and ou_parts[2] == "Lapa":
            if ou_parts[1] == "Matriz":
                return ou_parts[0]
            return ou_parts[1]
        elif len(ou_parts) >= 1:
            return ou_parts[0]
        else:
            return None
    except Exception as e:
        print(f"Erro ao extrair a OU: {e}")
        return None

# Configuração do Flask-Mail
app.config.update(
    MAIL_SERVER='smtp.office365.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='vinicius.muller@bj.coop.br',
    MAIL_PASSWORD='Vms071999'
)
mail = Mail(app)

def enviar_email(destinatario, assunto, corpo):
    with app.app_context():
        msg = Message(assunto, recipients=[destinatario], sender='vinicius.muller@bj.coop.br')
        msg.html = corpo
        mail.send(msg)

def enviar_email_assincrono(destinatario, assunto, corpo):
    # Função para enviar email em segundo plano
    thread = Thread(target=enviar_email, args=(destinatario, assunto, corpo))
    thread.start()


def get_versao():
    try:
        with open('VERSION', 'r') as f:
            return f.read().strip()
    except Exception:
        return ''

@app.route('/')
@login_required
def index():
    versao = get_versao()
    # CORREÇÃO: Não precisa mais passar 'user' para o template, o Flask-Login já disponibiliza 'current_user'
    return render_template('index.html', versao=versao)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        ldap_user_data = authenticate(username, password)
        
        if ldap_user_data:
            # Procura ou cria o usuário no banco de dados local
            user = User.get_by_username(ldap_user_data['username'])
            
            conn = get_db_connection()
            cursor = conn.cursor()

            if user is None: # Se o usuário não existe, cria
                is_admin = ldap_user_data['username'] in ADMIN_USERNAMES
                cursor.execute(
                    "INSERT INTO usuarios (username, email, full_name, is_admin) VALUES (%s, %s, %s, %s)",
                    (ldap_user_data['username'], ldap_user_data['email'], ldap_user_data['full_name'], is_admin)
                )
                conn.commit()
                user = User.get_by_username(ldap_user_data['username']) # Recarrega o usuário com o ID
            else: # Se o usuário já existe, atualiza os dados
                is_admin = ldap_user_data['username'] in ADMIN_USERNAMES
                cursor.execute(
                    "UPDATE usuarios SET email = %s, full_name = %s, is_admin = %s WHERE username = %s",
                    (ldap_user_data['email'], ldap_user_data['full_name'], is_admin, ldap_user_data['username'])
                )
                conn.commit()
                user = User.get(user.id) # Recarrega para garantir dados atualizados
            
            cursor.close()
            conn.close()

            login_user(user) # Inicia a sessão com Flask-Login
            
            # Salva a OU na sessão, pois é específica da sessão
            session['user_ou'] = get_user_ou(ldap_user_data['distinguished_name'])

            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciais inválidas. Tente novamente.', 'danger')

    return render_template('login.html', versao=get_versao())

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('Logoff realizado com sucesso!', 'success')
    return redirect(url_for('login'))

@app.route('/solicitar', methods=['GET', 'POST'])
@login_required
def solicitar_toner():
    user_ou = session.get('user_ou')  # Obtém a OU do usuário logado
    is_admin = current_user.is_admin  # Verifica se o usuário é administrador

    # Lógica de visualização de entrepostos e setores
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if is_admin:
        # Administradores podem ver todos os entrepostos e setores
        cursor.execute("SELECT id, entreposto FROM entrepostos")
        entrepostos_visiveis = cursor.fetchall()

        cursor.execute("SELECT id, setor FROM setores")
        setores_visiveis = cursor.fetchall()
    else:
        regras = OU_ENTREPOSTOS_SETORES.get(user_ou, {"entrepostos": [], "setores": []})
        entrepostos_ids = regras["entrepostos"]
        setores_ids = regras["setores"]

        # Buscar os nomes dos entrepostos permitidos
        cursor.execute("SELECT id, entreposto FROM entrepostos WHERE id IN (%s)" % ','.join(['%s'] * len(entrepostos_ids)), tuple(entrepostos_ids))
        entrepostos_visiveis = cursor.fetchall()

        # Filtrar apenas os setores definidos para a OU, independente do entreposto
        if setores_ids:
            cursor.execute(
                "SELECT id, setor FROM setores WHERE id IN (%s)" % ','.join(['%s'] * len(setores_ids)),
                tuple(setores_ids)
            )
            setores_visiveis = cursor.fetchall()
        else:
            setores_visiveis = []

    cursor.close()
    conn.close()

    if request.method == 'POST':
        entreposto_id = request.form['entreposto']

        # Corrigido para verificar os entrepostos '01 - Sede' e '03 - Boqueirão'
        if entreposto_id == '1':
            setor_id = request.form['setor']  # Setores específicos para Sede
        elif entreposto_id == '3':
            setor_id = request.form['setor']  # Setores específicos para Boqueirão
        else:
            setor_id = "15"  # Código padrão caso o entreposto não exija setor

        modelo_id = request.form['modelo']
        quantidade = request.form['quantidade']

        try:
            # Conectar ao banco para buscar nomes e inserir dados
            conn = get_db_connection()
            cursor = conn.cursor()

            # Consultar o nome do entreposto
            cursor.execute("SELECT entreposto FROM entrepostos WHERE id = %s", (entreposto_id,))
            entreposto_nome = cursor.fetchone()
            entreposto_nome = entreposto_nome[0] if entreposto_nome else "Desconhecido"

            # Consultar o nome do setor
            cursor.execute("SELECT setor FROM setores WHERE id = %s", (setor_id,))
            setor_nome = cursor.fetchone()
            setor_nome = setor_nome[0] if setor_nome else "Desconhecido"

            # Consultar o nome do modelo de impressora
            cursor.execute("SELECT impressora FROM impressoras WHERE id = %s", (modelo_id,))
            modelo_nome = cursor.fetchone()
            modelo_nome = modelo_nome[0] if modelo_nome else "Desconhecido"

            # MODIFICADO: Insere o user_id em vez de nome e email
            cursor.execute('''
                INSERT INTO pedidos (user_id, entreposto_id, setor_id, impressora_id, quantidade) 
                VALUES (%s, %s, %s, %s, %s)
            ''', (current_user.id, entreposto_id, setor_id, modelo_id, quantidade))
            conn.commit()

            cursor.close()
            conn.close()

            # Enviar e-mail de notificação ao administrador
            assunto_admin = 'Nova solicitação de tonner de ' + current_user.full_name
            corpo_admin = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #2c3e50;
                background-color: #f9f9f9;
            }}
            .container {{
                width: 100%;
                max-width: 600px;
                margin: auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            .logo-placeholder {{
                text-align: center;
                background-color: #dcdcdc;
                margin-bottom: 20px;
                padding: 10px;
            }}
            h2 {{
                color: #2c3e50;
                text-align: center;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            table th, table td {{
                padding: 12px;
                border: 1px solid #e0e0e0;
                text-align: left;
            }}
            table th {{
                background-color: #f2f2f2;
                font-weight: bold;
            }}
            .button-link {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #245844;
                color: #ffffff;
                text-decoration: none;
                border-radius: 5px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
            }}
            .button-link:hover {{
                background-color: #43a17d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo-placeholder">
                <img src="https://i.imgur.com/9uWvbNC.png" alt="Logo da Empresa" width="150" height="auto">
            </div>
            <h2>Nova Solicitação de Tonner</h2>
            <p>Um novo pedido foi feito por <strong>{current_user.full_name}</strong>.</p>
            
            <table>
                <tr>
                    <th>Entreposto</th>
                    <td>{entreposto_nome}</td>
                </tr>
                <tr>
                    <th>Setor</th>
                    <td>{setor_nome}</td>
                </tr>
                <tr>
                    <th>Modelo</th>
                    <td>{modelo_nome}</td>
                </tr>
                <tr>
                    <th>Quantidade</th>
                    <td>{quantidade}</td>
                </tr>
            </table>
            
            <p style="text-align: center;">
                <a href="http://toner.bj.coop.br/admin_pedidos" class="button-link">Exibir pedidos</a>
            </p>
        </div>
    </body>
    </html>
    """
            for admin in EMAIL_ADMIN_GROUP:
                enviar_email_assincrono(admin, assunto_admin, corpo_admin)

            # Enviar e-mail de confirmação para o usuário
            assunto_usuario = 'Seu pedido de Toner foi recebido!'
            corpo_usuario = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #2c3e50;
                background-color: #f9f9f9;
            }}
            .container {{
                width: 100%;
                max-width: 600px;
                margin: auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            .logo-placeholder {{
                text-align: center;
                background-color: #dcdcdc;
                margin-bottom: 20px;
                padding: 10px;
            }}
            h2 {{
                color: #2c3e50;
                text-align: center;
                margin-bottom: 20px;
            }}
            .message {{
                text-align: center;
                font-size: 18px;
                margin-bottom: 30px;
            }}
            .image-placeholder {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .image-placeholder img {{
                max-width: 100px;
                height: auto;
            }}
            .button-link {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #245844;
                color: #ffffff;
                text-decoration: none;
                border-radius: 5px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
            }}
            .button-link:hover {{
                background-color: #43a17d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo-placeholder">
                <img src="https://i.imgur.com/9uWvbNC.png" alt="Logo da Empresa" width="150" height="auto">
            </div>
            <h2>Pedido de Tonner Recebido</h2>
            <div class="message">
                <p>Seu pedido foi recebido e está sendo processado. Agradecemos pela sua solicitação.</p>
            </div>
            <div class="image-placeholder">
                <img src="https://i.imgur.com/w30vp1p.png" alt="Processamento em andamento">
            </div>
            <p style="text-align: center;">
                <a href="http://toner.bj.coop.br/meus_pedidos" class="button-link">Verificar Status do Pedido</a>
            </p>
        </div>
    </body>
    </html>
    """
            enviar_email_assincrono(current_user.email, assunto_usuario, corpo_usuario)

            return redirect(url_for('index'))
        except Exception as e:
            print(f"Erro ao processar o pedido: {e}")
            return render_template('solicitar_toner.html', user=current_user, entrepostos_visiveis=entrepostos_visiveis, setores_visiveis=setores_visiveis, is_admin=is_admin)

    return render_template(
        'solicitar_toner.html',
        entrepostos_visiveis=entrepostos_visiveis,
        setores_visiveis=setores_visiveis,
    )

@app.route('/get_setores/<int:entreposto_id>')
@login_required
def get_setores(entreposto_id):
    user_ou = session.get('user_ou')
    is_admin = current_user.is_admin

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if is_admin:
        if entreposto_id == 1:
            setores_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        elif entreposto_id == 3:
            setores_ids = [11, 12, 13, 14]
        else:
            setores_ids = [15]

        query = "SELECT id, setor FROM setores WHERE id IN (%s)" % (
            ','.join(['%s'] * len(setores_ids))
        )
        cursor.execute(query, setores_ids)
    else:
        regras = OU_ENTREPOSTOS_SETORES.get(user_ou, {"entrepostos": [], "setores": []})
        
        if entreposto_id in regras["entrepostos"]:
            setores_ids = regras["setores"]
            setores_permitidos = [s for s in setores_ids if s]
            if setores_permitidos:
                query = "SELECT id, setor FROM setores WHERE id IN (%s)" % (
                    ','.join(['%s'] * len(setores_permitidos))
                )
                cursor.execute(query, setores_permitidos)
            else:
                return jsonify([])
        else:
            return jsonify([])

    setores = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(setores)



@app.route('/meus_pedidos')
@login_required
def meus_pedidos():
    # Também fica muito mais simples
    return render_template('meus_pedidos.html', is_admin=False)

@app.route('/admin')
@admin_required
def admin_page():
    return render_template('administracao.html')

@app.route('/admin_pedidos')
@admin_required
def admin_page_pedidos():
    # A rota agora é muito mais simples!
    return render_template('adm_pedidos.html', is_admin=True)


# Rota para cancelar o pedido
@app.route('/cancelar_pedido/<int:pedido_id>', methods=['POST'])
@login_required
def cancelar_pedido(pedido_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Atualiza o status do pedido para '3' (Cancelado)
        cursor.execute('''
                       UPDATE pedidos
                       SET status_id = 3, quantidade = 0 
                       WHERE id = %s''', (pedido_id,))
        conn.commit()
        response = {'success': True}
    except Exception as e:
        print(f"Erro ao cancelar pedido: {e}")
        response = {'success': False}
    finally:
        cursor.close()
        conn.close()

    return jsonify(response)

# Rota para enviar o pedido
@app.route('/enviar_pedido/<int:pedido_id>', methods=['POST'])
@admin_required
def enviar_pedido(pedido_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('UPDATE pedidos SET status_id = 1 WHERE id = %s', (pedido_id,))
        conn.commit()

        # MODIFICADO: Consulta robusta usando user_id
        cursor.execute('''
            SELECT u.email as email_usuario, e.entreposto, s.setor, i.impressora, p.quantidade
            FROM pedidos p
            JOIN usuarios u ON p.user_id = u.id
            JOIN entrepostos e ON p.entreposto_id = e.id
            JOIN setores s ON p.setor_id = s.id
            JOIN impressoras i ON p.impressora_id = i.id
            WHERE p.id = %s
        ''', (pedido_id,))
        pedido = cursor.fetchone()

        if pedido and pedido['email_usuario']:
            # Enviar e-mail para o usuário
            assunto_usuario = 'Seu pedido de Tonner foi enviado'
            corpo_usuario = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #2c3e50;
                        background-color: #f9f9f9;
                    }}
                    .container {{
                        width: 100%;
                        max-width: 600px;
                        margin: auto;
                        background-color: #ffffff;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    }}
                    .logo-placeholder {{
                        text-align: center;
                        background-color: #dcdcdc;
                        margin-bottom: 20px;
                        padding: 10px;
                    }}
                    h2 {{
                        color: #2c3e50;
                        text-align: center;
                        margin-bottom: 20px;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 20px;
                    }}
                    table th, table td {{
                        padding: 12px;
                        border: 1px solid #e0e0e0;
                        text-align: left;
                    }}
                    table th {{
                        background-color: #f2f2f2;
                        font-weight: bold;
                    }}
                    .button-link {{
                        display: inline-block;
                        padding: 10px 20px;
                        background-color: #245844;
                        color: #ffffff;
                        text-decoration: none;
                        border-radius: 5px;
                        text-align: center;
                        font-size: 14px;
                        font-weight: bold;
                    }}
                    .button-link:hover {{
                        background-color: #43a17d;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo-placeholder">
                        <img src="https://i.imgur.com/9uWvbNC.png" alt="Logo da Empresa" width="150" height="auto">
                    </div>
                    <h2>Pedido de Tonner Enviado</h2>
                    <p>Seu pedido foi enviado com sucesso. Seguem os detalhes:</p>
                    
                    <table>
                        <tr>
                            <th>Entreposto</th>
                            <td>{pedido['entreposto']}</td>
                        </tr>
                        <tr>
                            <th>Setor</th>
                            <td>{pedido['setor']}</td>
                        </tr>
                        <tr>
                            <th>Modelo</th>
                            <td>{pedido['impressora']}</td>
                        </tr>
                        <tr>
                            <th>Quantidade</th>
                            <td>{pedido['quantidade']}</td>
                        </tr>
                    </table>
                    
                    <p style="text-align: center;">
                        <a href="http://toner.bj.coop.br/meus_pedidos" class="button-link">Verificar Status do Pedido</a>
                    </p>
                </div>
            </body>
            </html>
            """
            enviar_email_assincrono(pedido['email_usuario'], assunto_usuario, corpo_usuario)

        response = {'success': True}
    except Exception as e:
        print(f"Erro ao enviar pedido: {e}")
        response = {'success': False}
    finally:
        cursor.close()
        conn.close()

    return jsonify(response)

@app.route('/estoque')
@admin_required  # Acesso restrito aos administradores
def estoque():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Consulta a view_estoque para obter o nome da impressora e a quantidade disponível
    cursor.execute('''
        SELECT impressora, quantidade
        FROM view_estoque
    ''')
    estoque = cursor.fetchall()
    print("Dados de estoque:", estoque)

    cursor.close()
    conn.close()

    # Renderiza a página estoque.html com os dados de estoque
    return render_template('estoque.html', estoque=estoque, user=current_user.full_name)

@app.route('/adicionar_tonner', methods=['POST'])
@login_required  # Garante que o usuário esteja logado
def adicionar_tonner():
    data = request.get_json()
    impressora = data['impressora']  # ID da impressora
    quantidade = data['quantidade']  # Quantidade a ser adicionada
    usuario_logado = current_user.full_name  # Nome do usuário logado

    # Verifica se os campos estão preenchidos
    if not impressora or not quantidade:
        return jsonify(success=False, message='Dados incompletos')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insere os dados na tabela entrada_estoque
        cursor.execute('INSERT INTO entrada_estoque (nomeFunc, impressora_id, quantidade) VALUES (%s, %s, %s)',
                       (usuario_logado, impressora, quantidade))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify(success=True, message='Tonners adicionados com sucesso!')
    except Exception as e:
        print(f'Erro ao adicionar tonners: {e}')
        return jsonify(success=False, message='Erro ao adicionar tonners')

@app.route('/historico_estoque', methods=['GET'])
@login_required
def historico_estoque():
    try:
        # Abrindo conexão com o banco de dados
        conn = get_db_connection()
        cursor = conn.cursor()

        # Consulta os dados da view_entrada_estoque
        query = "SELECT Usuario, impressora, quantidade, data_entrada FROM view_entrada_estoque"
        cursor.execute(query)
        result = cursor.fetchall()

        # Transformando os resultados em uma lista de dicionários
        historico = []
        for row in result:
            historico.append({
                'Usuario': row[0], 
                'impressora': row[1],
                'quantidade': row[2],
                'data_entrada': row[3]
            })

        cursor.close()
        conn.close()

        # Retornando os dados em formato JSON
        return jsonify(historico)

    except Exception as e:
        print(f"Erro ao buscar o histórico: {e}")
        return jsonify({'error': 'Erro ao buscar o histórico'}), 500

@app.route('/dados_relatorios')
@login_required
def dados_relatorios():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Consulta para o gráfico de quantidade por modelo de impressora
    cursor.execute('SELECT impressora AS Impressora, total_tonners AS Quantidade FROM view_top_impressoras GROUP BY Impressora ORDER BY Quantidade DESC')
    impressora_data = cursor.fetchall()
    print(impressora_data)

    # Consulta para o gráfico de quantidade por entreposto
    cursor.execute('SELECT Entreposto AS Entreposto, Quantidade AS Quantidade FROM view_top_entrepostos GROUP BY Entreposto ORDER BY Quantidade DESC')
    entreposto_data = cursor.fetchall()
    print(entreposto_data)

    # Consulta para o gráfico de quantidade por setor da sede
    cursor.execute('SELECT setor AS Setor, total_tonners AS Quantidade FROM view_top_setores_sede GROUP BY setor ORDER BY Quantidade DESC')
    setor_sede_data = cursor.fetchall()
    print(setor_sede_data)

    # Consulta para o gráfico de quantidade por setor do Boqueirão
    cursor.execute('SELECT setor AS Setor, total_tonners AS Quantidade FROM view_top_setores_boq GROUP BY setor ORDER BY Quantidade DESC')
    setor_boqueirao_data = cursor.fetchall()
    print(setor_boqueirao_data)

    # Consulta para a tabela de top 10 usuários
    cursor.execute('SELECT Nome AS Usuario, quantidade AS Quantidade FROM view_top_users GROUP BY Nome ORDER BY quantidade DESC')
    top_users_data = cursor.fetchall()
    print(top_users_data)

    # Formatação dos dados para o frontend
    data = {
        'impressora': {
            'labels': [item['Impressora'] for item in impressora_data],
            'data': [item['Quantidade'] for item in impressora_data]
        },
        'entreposto': {
            'labels': [item['Entreposto'] for item in entreposto_data],
            'data': [item['Quantidade'] for item in entreposto_data]
        },
        'setor_sede': {
            'labels': [item['Setor'] for item in setor_sede_data],
            'data': [item['Quantidade'] for item in setor_sede_data]
        },
        'setor_boqueirao': {
            'labels': [item['Setor'] for item in setor_boqueirao_data],
            'data': [item['Quantidade'] for item in setor_boqueirao_data]
        },
        'top_users': [{'usuario': item['Usuario'], 'quantidade': item['Quantidade']} for item in top_users_data]
    }


    cursor.close()
    conn.close()

    return jsonify(data)

# ROTA DE API PARA A TABELA DE ADMIN - ATUALIZADA
@app.route('/api/dados_pedidos_admin')
@admin_required
def dados_pedidos_admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    
    column_map = ['pedido_id', 'nomeFunc', 'Entreposto', 'Setor', 'Impressora', 'Quantidade', 'Status', 'data_pedido']
    order_column_index = request.args.get('order[0][column]', 0, type=int)
    order_dir = request.args.get('order[0][dir]', 'desc', type=str)
    order_column = column_map[order_column_index] if 0 <= order_column_index < len(column_map) else 'pedido_id'

    base_query = "FROM view_pedidos"
    where_clauses = []
    params = []

    global_search_value = request.args.get('search[value]')
    if global_search_value:
        search_term = f"%{global_search_value}%"
        global_where = " OR ".join([f"{col} LIKE %s" for col in ['nomeFunc', 'Entreposto', 'Setor', 'Impressora', 'Status']])
        where_clauses.append(f"({global_where})")
        params.extend([search_term] * 5)

    # Adiciona os filtros de colunas individuais
    for i in range(len(column_map)):
        search_value = request.args.get(f'columns[{i}][search][value]')
        if search_value:
            # NOVO: LÓGICA PARA FILTRO DE DATA
            if column_map[i] == 'data_pedido' and ' to ' in search_value:
                start_date, end_date = search_value.split(' to ')
                where_clauses.append("DATE(data_pedido) BETWEEN %s AND %s")
                params.extend([start_date, end_date])
            elif '|' in search_value:
                parts = [p.strip('^$') for p in search_value.split('|')]
                placeholders = ', '.join(['%s'] * len(parts))
                where_clauses.append(f"{column_map[i]} IN ({placeholders})")
                params.extend(parts)
            elif search_value.startswith('^') and search_value.endswith('$'):
                where_clauses.append(f"{column_map[i]} = %s")
                params.append(search_value.strip('^$'))
            else:
                where_clauses.append(f"{column_map[i]} LIKE %s")
                params.append(f"%{search_value}%")
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    # Contagem de registros
    cursor.execute(f"SELECT COUNT(pedido_id) as total {base_query}")
    records_total = cursor.fetchone()['total']
    cursor.execute(f"SELECT COUNT(pedido_id) as total {base_query} {where_sql}", tuple(params))
    records_filtered = cursor.fetchone()['total']

    # Query principal
    query = f"""
        SELECT pedido_id, nomeFunc, Entreposto, Setor, Impressora, Quantidade, Status, data_pedido 
        {base_query} {where_sql}
        ORDER BY {order_column} {order_dir}
        LIMIT %s OFFSET %s
    """
    final_params = list(params)
    final_params.extend([length, start])
    cursor.execute(query, tuple(final_params))
    pedidos = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    for pedido in pedidos:
        if pedido['Status'] == 'Não Enviado':
            pedido['acoes'] = f"""
                <div class="action-buttons-container">
                    <button class="dt-button-cancel" onclick="cancelarPedido({pedido['pedido_id']})">Cancelar</button>
                    <button class="dt-button-send" onclick="enviarPedido({pedido['pedido_id']})">Enviar</button>
                </div>"""
        else:
            pedido['acoes'] = '-'

    return jsonify({
        'draw': draw, 'recordsTotal': records_total,
        'recordsFiltered': records_filtered, 'data': pedidos
    })


# ROTA DE API PARA "MEUS PEDIDOS" - ATUALIZADA
@app.route('/api/dados_meus_pedidos')
@login_required
def dados_meus_pedidos():
    user_ou = session.get('user_ou')
    regras = OU_ENTREPOSTOS_SETORES.get(user_ou, {"entrepostos": [], "setores": []})
    
    if not regras["entrepostos"] or not regras["setores"]:
        return jsonify({'draw': request.args.get('draw', type=int), 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    order_column_index = request.args.get('order[0][column]', 0, type=int)
    order_dir = request.args.get('order[0][dir]', 'desc', type=str)
    
    column_map = ['pedido_id', 'nomeFunc', 'Entreposto', 'Setor', 'Impressora', 'Quantidade', 'Status', 'data_pedido']
    order_column = column_map[order_column_index] if 0 <= order_column_index < len(column_map) else 'pedido_id'

    base_query = "FROM view_pedidos_entrepostos2"
    where_clauses = [
        "entreposto_id IN ({})".format(','.join(['%s'] * len(regras["entrepostos"]))),
        "setor_id IN ({})".format(','.join(['%s'] * len(regras["setores"])))
    ]
    params = list(regras["entrepostos"]) + list(regras["setores"])
    
    global_search_value = request.args.get('search[value]')
    if global_search_value:
        search_term = f"%{global_search_value}%"
        global_where = " OR ".join([f"{col} LIKE %s" for col in ['nomeFunc', 'Entreposto', 'Setor', 'Impressora', 'Status']])
        where_clauses.append(f"({global_where})")
        params.extend([search_term] * 5)

    # Adicionar filtros das colunas
    for i in range(len(column_map)):
        search_value = request.args.get(f'columns[{i}][search][value]')
        if search_value:
            # NOVO: LÓGICA PARA FILTRO DE DATA
            if column_map[i] == 'data_pedido' and ' to ' in search_value:
                start_date, end_date = search_value.split(' to ')
                where_clauses.append("DATE(data_pedido) BETWEEN %s AND %s")
                params.extend([start_date, end_date])
            elif '|' in search_value:
                parts = [p.strip('^$') for p in search_value.split('|')]
                placeholders = ', '.join(['%s'] * len(parts))
                where_clauses.append(f"{column_map[i]} IN ({placeholders})")
                params.extend(parts)
            elif search_value.startswith('^') and search_value.endswith('$'):
                where_clauses.append(f"{column_map[i]} = %s")
                params.append(search_value.strip('^$'))
            else:
                where_clauses.append(f"{column_map[i]} LIKE %s")
                params.append(f"%{search_value}%")

    where_sql = "WHERE " + " AND ".join(where_clauses)
    
    # Contagem de registros
    count_total_params = tuple(list(regras["entrepostos"]) + list(regras["setores"]))
    cursor.execute(f"SELECT COUNT(pedido_id) as total {base_query} WHERE entreposto_id IN ({','.join(['%s'] * len(regras['entrepostos']))}) AND setor_id IN ({','.join(['%s'] * len(regras['setores']))})", count_total_params)
    records_total = cursor.fetchone()['total']

    count_filtered_params = tuple(params)
    cursor.execute(f"SELECT COUNT(pedido_id) as total {base_query} {where_sql}", count_filtered_params)
    records_filtered = cursor.fetchone()['total']

    # Query principal
    query = f"""
        SELECT pedido_id, nomeFunc, Entreposto, Setor, Impressora, Quantidade, Status, data_pedido 
        {base_query} {where_sql}
        ORDER BY {order_column} {order_dir}
        LIMIT %s OFFSET %s
    """
    params.extend([length, start])
    cursor.execute(query, tuple(params))
    pedidos = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        'draw': draw, 'recordsTotal': records_total,
        'recordsFiltered': records_filtered, 'data': pedidos
    })

# NOVA ROTA PARA OBTER OPÇÕES DE FILTRO
@app.route('/api/filter_options')
@login_required
def get_filter_options():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    options = {}
    
    # Usamos a view_pedidos para garantir que só apareçam opções que existem nos pedidos
    cursor.execute("SELECT DISTINCT Entreposto FROM view_pedidos ORDER BY Entreposto")
    options['entrepostos'] = [row['Entreposto'] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT Setor FROM view_pedidos ORDER BY Setor")
    options['setores'] = [row['Setor'] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT Impressora FROM view_pedidos ORDER BY Impressora")
    options['impressoras'] = [row['Impressora'] for row in cursor.fetchall()]
    
    # Status pode ser uma lista fixa
    options['status'] = ['Não Enviado', 'Enviado', 'Cancelado']

    cursor.close()
    conn.close()
    
    return jsonify(options)

@app.route('/dashboard')
@login_required
def relatorios():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, host="localhost", port=80)


