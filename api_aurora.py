from fastapi import FastAPI, APIRouter, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
from typing import Optional, List  # Aqui já resolve todos os tipos
from datetime import date, time
from fastapi.responses import FileResponse
import os
from fastapi.staticfiles import StaticFiles
import json

app = FastAPI(title="Aurora Bartenders API")

# ==========================================
# CLASSES
# ==========================================

class EventoUpdate(BaseModel):
    responsavel: Optional[str] = ""
    telefone: Optional[str] = ""
    dataEvento: Optional[date] = None
    horaEvento: Optional[time] = None
    durH: Optional[int] = 4
    durM: Optional[int] = 0
    extH: Optional[int] = 0
    extM: Optional[int] = 0
    termino: Optional[time] = None
    local: Optional[str] = ""
    valorContrato: Optional[float] = 0.0
    valorHoraExtra: Optional[float] = 0.0
    valorCustosAdicionais: Optional[float] = 0.0
    descCustosAdicionais: Optional[str] = ""
    sinalPerc: Optional[float] = 0.0
    contratante: Optional[str] = None
    cnpj_cpf: Optional[str] = None

# ... (suas configurações de app e rotas antigas) ...

class NovaRegraPacote(BaseModel):
    account_id: str
    categoria_generica: str
    pacote: str
    real_ingredient_id: str

class EventCreate(BaseModel):
    nome: str
    account_id: str # <--- AGORA É OBRIGATÓRIO E SEM PADRÃO!
    responsavel: Optional[str] = ""
    telefone: Optional[str] = ""
    dataEvento: Optional[date] = None
    horaEvento: Optional[time] = None
    durH: Optional[int] = 4
    durM: Optional[int] = 0
    extH: Optional[int] = 0
    extM: Optional[int] = 0
    termino: Optional[time] = None
    local: Optional[str] = ""

# O "Molde" (Schema) para criar um evento
class NovoEvento(BaseModel):
    account_id: str
    event_name: str
    event_date: str          # Formato esperado: 'YYYY-MM-DD'
    custom_url_slug: str     # Ex: 'niver-do-heitor'
    status: Optional[str] = 'confirmed' # Se o app não mandar, assume 'confirmed'

class NovoInsumo(BaseModel):
    account_id: str
    name: str
    brand: Optional[str] = ""
    type_name: str
    measurement_unit: str
    package_quantity: float
    current_cost_price: float # Adicionado para salvar o preço inicial

class NovaCompra(BaseModel):
    ingredient_id: str
    packages_bought: float
    total_paid: float
    supplier_name: Optional[str] = "Não informado"


class PedidoSimulacaoCusto(BaseModel):
    account_id: str
    drink_ids: List[str]
    pacote: str  # Ex: 'bronze', 'prata', 'ouro', 'diamante'

class IngredienteReceita(BaseModel):
    ingredient_id: str
    quantity: float # Ex: 50 (para 50ml)

class NovoCocktail(BaseModel):
    account_id: str
    name: str
    preparation_steps: Optional[str] = ""
    category: str
    technique: Optional[str] = "Montado"     # <--- ADICIONADO!
    drink_type: Optional[str] = "Cocktail"   # <--- ADICIONADO!
    sale_price: float
    image_url: Optional[str] = ""
    min_package_level: int = 1
    recipe: List[IngredienteReceita]

class EdicaoInsumo(BaseModel):
    name: str
    brand: Optional[str] = ""
    type_name: str
    measurement_unit: str
    package_quantity: float
    current_cost_price: float

class NovoMenu(BaseModel):
    # Uma lista contendo os UUIDs dos drinks, na ordem em que devem aparecer na tela
    drinks: List[str] 

class ItemCarga(BaseModel):
    ingredient_id: str
    quantity: float

class CargaEventoBody(BaseModel):
    event_id: str
    itens: List[ItemCarga] # 🛑 O molde agora usa "items" (com m) para bater com o JS!

# 1. O Molde do que o seu PDV (index.html) vai enviar para a API
class NovaVenda(BaseModel):
    event_id: str
    cocktail_id: str
    price: float  # Se for Open Bar, o PDV vai mandar 0.00. Se for Cash Bar, manda o valor pago.
    user_name: Optional[str] = "Bartender"

class EstornoVenda(BaseModel):
    sale_id: str
    event_id: str

class NovoMembro(BaseModel):
    account_id: str
    name: str
    phone: str
    role: Optional[str] = "Bartender"
    status: Optional[str] = "ativo"
    cpf: Optional[str] = ""
    birth_date: Optional[str] = None
    gender: Optional[str] = ""
    base_fee: Optional[float] = 0.0
    additional_fee: Optional[float] = 0.0

class EditaMembro(BaseModel):
    account_id: str
    name: str
    phone: str
    role: str
    cpf: Optional[str] = ""
    birth_date: Optional[str] = None
    gender: Optional[str] = ""
    base_fee: Optional[float] = 0.0
    additional_fee: Optional[float] = 0.0

class EventStatus(BaseModel):
    status: str

# Molde para receber a atualização de estoque
class EstoqueDrink(BaseModel):
    quantidade: int

# 1. MODELO DE ENTRADA CORRIGIDO CONFORME A TABELA BUDGET
class NovoOrcamentoInput(BaseModel):
    id: Optional[str] = None  # <--- NOVA LINHA AQUI
    account_id: str
    cliente: str
    data_evento: Optional[str] = None
    local: Optional[str] = None
    qtd_pessoas: int
    valor_pessoa: float
    extras: float
    total: float
    pacote_escolhido: str  # 100% alinhado com a coluna 8
    drinks: List[dict]     # Recebe a lista de objetos do JS diretamente
    custo_estimado: float
    valor_sugerido: float

class ItemRetorno(BaseModel):
    ingredient_id: str
    returned_quantity: float

class PayloadRetorno(BaseModel):
    itens: List[ItemRetorno]

class CloneCocktail(BaseModel):
    account_id: str
    novo_nome: Optional[str] = None # Opcional: permite que o frontend já mande o nome desejado

# ==========================================
# ROTAS DO FRONTEND (Telas HTML)
# ==========================================
@app.get("/login.html")
def abrir_tela_login():
    return FileResponse("login.html")

@app.get("/admin.html")  # Aproveite e já libere o painel também!
def abrir_tela_admin():
    return FileResponse("admin.html")


# ==========================================
# CONFIGURAÇÃO DE SEGURANÇA (CORS)
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite que qualquer front-end (até o seu localhost) acesse a API
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os comandos (GET, POST, etc.)
    allow_headers=["*"],  # Permite qualquer formato de cabeçalho
)

# Libera a pasta de imagens para acesso público
app.mount("/imagens", StaticFiles(directory="imagens"), name="imagens")


# ==========================================
# ROTA DE REGRAS: SALVAR / ATUALIZAR REGRA DE PACOTE
# ==========================================
@app.post("/package-rules")
def salvar_regra_pacote(regra: NovaRegraPacote):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        nova_regra_id = str(uuid.uuid4())
        
        # 1. Limpa a regra antiga se ela já existir para evitar duplicidade
        cur.execute("""
            DELETE FROM package_rules 
            WHERE account_id = %s AND categoria_generica = %s AND pacote = %s;
        """, (regra.account_id, regra.categoria_generica, regra.pacote))
        
        # 2. Insere a nova regra
        query_insert = """
            INSERT INTO package_rules (id, account_id, categoria_generica, pacote, real_ingredient_id)
            VALUES (%s, %s, %s, %s, %s);
        """
        cur.execute(query_insert, (
            nova_regra_id, regra.account_id, regra.categoria_generica, 
            regra.pacote, regra.real_ingredient_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "mensagem": "Regra salva com sucesso!"}
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA: VERIFICAR STATUS DO EVENTO (GET)
# Para o PDV parar de dar erro 405
# ==========================================
@app.get("/events/{event_id}/status")
def checar_status_evento(event_id: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Busca o status na tabela events
        cur.execute("SELECT status FROM events WHERE id::text = %s OR custom_url_slug = %s", (event_id, event_id))
        evento = cur.fetchone()
        
        if evento:
            return {"status": "sucesso", "evento_status": evento['status']}
        else:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
            
    except Exception as e:
        print(f"Erro ao checar status do evento: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")
    finally:
        cur.close()
        conn.close()

# ==========================================
# ROTAS DE FRONTEND (TELAS HTML E PWA)
# ==========================================
@app.get("/kds.html")
def tela_kds():
    return FileResponse("kds.html")

@app.get("/index.html")
def tela_pdv():
    return FileResponse("index.html")

@app.get("/cardapio.html")
def tela_cardapio():
    return FileResponse("cardapio.html")

@app.get("/admin.html")
def tela_admin():
    return FileResponse("admin.html")

# --- Adicione estes dois para parar de dar erro 404 no console ---
@app.get("/sw.js")
def service_worker():
    return FileResponse("sw.js")

@app.get("/manifest.json")
def manifest():
    return FileResponse("manifest.json")

@app.get("/icon-192.png")
def icon_192():
    return FileResponse("icon-192.png")

@app.get("/icon-512.png")
def icon_512():
    return FileResponse("icon-512.png")

# ==========================================
# ROTA MESTRA (NO TOPO!): LISTAR EVENTOS ATIVOS
# ==========================================
@app.get("/events/active")
@app.get("/eventos-ativos")
def listar_eventos_ativos(account_id: str): # 📍 1. EXIGE O ID DA AGÊNCIA AQUI
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id é obrigatório para listar eventos ativos")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")

    try:
        cur = conn.cursor()
        
        # 📍 2. O CADEADO TRIPLO: Ativado (TRUE), Aberto ('aberto') E da Agência Certa!
        cur.execute("""
            SELECT id, name 
            FROM events 
            WHERE is_active = TRUE 
            AND status = 'aberto' 
            AND account_id = %s
        """, (account_id,))
        
        eventos = cur.fetchall()
        cur.close()
        conn.close()

        # O seu tratamento de formatação continua intacto!
        dados_formatados = []
        for e in eventos:
            if isinstance(e, dict):
                dados_formatados.append({"id": str(e['id']), "event_name": str(e['name'])})
            else:
                dados_formatados.append({"id": str(e[0]), "event_name": str(e[1])})

        return {"status": "sucesso", "dados": dados_formatados}

    except Exception as e:
        if conn: conn.rollback()
        print(f"🔥 ERRO FATAL NA ROTA /eventos-ativos: {str(e)}") 
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# BUSCAR DETALHES DE UM EVENTO ESPECÍFICO (FASTAPI)
# ==========================================
@app.get("/events/{event_id}")
def buscar_detalhes_evento(event_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Busca o evento específico pelo ID
        sql = "SELECT * FROM events WHERE id = %s;"
        cur.execute(sql, (event_id,))
        evento = cur.fetchone()
        
        cur.close()
        conn.close()
        
        # Verifica se achou e devolve para o JavaScript
        if evento:
            # Converte datas e horas para texto para o JSON não reclamar
            if evento.get('event_date'):
                evento['event_date'] = str(evento['event_date'])
            if evento.get('start_time'):
                evento['start_time'] = str(evento['start_time'])
            if evento.get('end_time'):
                evento['end_time'] = str(evento['end_time'])
            if evento.get('created_at'):
                evento['created_at'] = str(evento['created_at'])
                
            return evento
        else:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
            
    except Exception as e:
        if conn:
            conn.close()
        print("Erro ao buscar evento:", e)
        raise HTTPException(status_code=500, detail="Falha interna no servidor")

# ==========================================
# ATUALIZAR DADOS DO EVENTO (SALVAR EDIÇÃO)
# ==========================================
@app.put("/events/{event_id}")
def atualizar_evento(event_id: str, dados: EventoUpdate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # O poderoso comando UPDATE do SQL
        query = """
            UPDATE events 
            SET 
                responsible_name = %s,
                phone = %s,
                event_date = %s,
                start_time = %s,
                duration_h = %s,
                duration_m = %s,
                extra_h = %s,
                extra_m = %s,
                end_time = %s,
                location = %s,
                contract_value = %s,
                extra_hour_value = %s,
                extra_costs_value = %s,
                extra_costs_desc = %s,
                upfront_perc = %s,
                contratante = %s,
                cnpj_cpf = %s
            WHERE id = %s
        """
        
        # A ordem aqui tem que ser EXATAMENTE igual a dos %s ali em cima!
        valores = (
            dados.responsavel,
            dados.telefone,
            dados.dataEvento,
            dados.horaEvento,
            dados.durH,
            dados.durM,
            dados.extH,
            dados.extM,
            dados.termino,
            dados.local,
            dados.valorContrato,
            dados.valorHoraExtra,
            dados.valorCustosAdicionais,
            dados.descCustosAdicionais,
            dados.sinalPerc,
            dados.contratante,
            dados.cnpj_cpf,
            event_id # O ID vai por último para o WHERE
        )
        
        cur.execute(query, valores)
        
        # Verifica se achou a linha para atualizar
        linhas_afetadas = cur.rowcount
        
        # O Commit é o que grava de verdade no Supabase!
        conn.commit()
        
        cur.close()
        conn.close()
        
        if linhas_afetadas == 0:
            raise HTTPException(status_code=404, detail="Evento não encontrado para atualizar")
            
        return {"status": "sucesso", "mensagem": "Dados atualizados com sucesso no banco!"}
        
    except Exception as e:
        if conn:
            conn.rollback() # Desfaz a operação se der erro
            conn.close()
        print("Erro no PUT /events:", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA DE INTELIGÊNCIA: SIMULADOR DE CUSTO POR PACOTE
# ==========================================
@app.post("/orcamentos/simular-custo")
def simular_custo_pacote(pedido: PedidoSimulacaoCusto):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")

    try:
        cur = conn.cursor()
        
        # A mágica do COALESCE com a sua estrutura de tabelas
        query = """
            SELECT 
                c.id AS drink_id,
                c.name AS drink_nome,
                ci.quantity AS qtd_ml_na_receita,
                gen_ing.name AS ingrediente_base,
                COALESCE(real_ing.name, gen_ing.name) AS ingrediente_usado,
                COALESCE(real_ing.current_cost_price, gen_ing.current_cost_price) AS preco_garrafa,
                COALESCE(real_ing.package_quantity, gen_ing.package_quantity) AS tamanho_garrafa
            FROM cocktails c
            JOIN cocktail_ingredients ci ON c.id = ci.cocktail_id
            JOIN ingredients gen_ing ON ci.ingredient_id = gen_ing.id
            LEFT JOIN package_rules pr 
                ON pr.categoria_generica = gen_ing.name 
                AND pr.pacote = %s 
                AND pr.account_id = %s
            LEFT JOIN ingredients real_ing ON pr.real_ingredient_id = real_ing.id
            WHERE c.id::text = ANY(%s) AND c.account_id = %s;
        """
        
        # O pedido.pacote vem como string ('bronze', 'prata', etc)
        cur.execute(query, (pedido.pacote, pedido.account_id, pedido.drink_ids, pedido.account_id))
        linhas = cur.fetchall()
        
        custo_total_selecao = 0
        drinks_calculados = {}

        for linha in linhas:
            d_id = linha[0]
            d_nome = linha[1]
            qtd_usada = float(linha[2]) if linha[2] else 0
            ing_nome = linha[4]
            preco = float(linha[5]) if linha[5] else 0
            tamanho = float(linha[6]) if linha[6] and float(linha[6]) > 0 else 1 

            # Matemática do custo real do insumo
            custo_ingrediente = (preco / tamanho) * qtd_usada

            if d_id not in drinks_calculados:
                drinks_calculados[d_id] = {
                    "nome": d_nome,
                    "custo_total_drink": 0,
                    "detalhes": []
                }
            
            drinks_calculados[d_id]["custo_total_drink"] += custo_ingrediente
            drinks_calculados[d_id]["detalhes"].append({
                "ingrediente": ing_nome,
                "qtd_usada_ml": qtd_usada,
                "custo_calculado": round(custo_ingrediente, 4) # Arredondando para não dar dízima
            })

            custo_total_selecao += custo_ingrediente

        cur.close()
        conn.close()

        return {
            "status": "sucesso",
            "pacote_simulado": pedido.pacote,
            "custo_base_todas_bebidas": round(custo_total_selecao, 2),
            "detalhe_por_drink": drinks_calculados
        }

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ingredients/")
def criar_insumo(insumo: NovoInsumo):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        cur = conn.cursor()
        
        # 1. Busca o ID do tipo pelo nome (ex: "Destilado")
        cur.execute("SELECT id FROM ingredient_types WHERE name = %s", (insumo.type_name,))
        tipo_row = cur.fetchone()
        tipo_id = tipo_row[0] if tipo_row else None 

        # 2. Insere o insumo
        query = """
            INSERT INTO ingredients 
            (account_id, name, brand, type_id, measurement_unit, package_quantity, current_cost_price, current_stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            RETURNING id;
        """
        cur.execute(query, (
            insumo.account_id, insumo.name, insumo.brand, tipo_id, 
            insumo.measurement_unit, insumo.package_quantity, insumo.current_cost_price
        ))
        
        conn.commit()
        return {"status": "sucesso", "mensagem": "Insumo cadastrado!"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()



# Função para conectar no banco (Agora segura!)
def get_db_connection():
    try:
        # Puxando a variável de ambiente segura do Render
        db_url = os.environ.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"Erro ao conectar no banco: {e}")
        return None

# ==========================================
# NOSSA PRIMEIRA ROTA (ENDPOINT)
# ==========================================
@app.get("/drinks/{account_id}/recipes")
def listar_drinks(account_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        # RealDictCursor faz o resultado voltar no formato JSON (chave: valor) 
        # igual o seu aplicativo lia no Firebase!
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Aquele nosso SELECT poderoso
        query = """
            SELECT 
                c.id,
                c.name AS drink_nome,
                c.category AS categoria,
                c.sale_price AS preco_venda,
                STRING_AGG(ci.quantity || i.measurement_unit || ' de ' || i.name, ', ') AS receita_completa
            FROM cocktails c
            LEFT JOIN cocktail_ingredients ci ON c.id = ci.cocktail_id
            LEFT JOIN ingredients i ON ci.ingredient_id = i.id
            WHERE c.account_id = %s
            GROUP BY 
                c.id, c.name, c.category, c.sale_price
            ORDER BY c.name;
        """
        
        # O %s evita ataques de injeção de SQL (segurança em primeiro lugar)
        cur.execute(query, (account_id,))
        drinks = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "quantidade": len(drinks), "dados": drinks}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        
# ==========================================
# NOSSA SEGUNDA ROTA: O CARDÁPIO PÚBLICO
# ==========================================
@app.get("/menu/{url_slug}")
def ver_cardapio_publico(url_slug: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # O SQL que une o Evento, o Menu e o Coquetel em uma cajadada só!
        query = """
            SELECT 
                e.name AS nome_da_festa,
                e.event_date AS data_da_festa,
                c.name AS nome_do_drink,
                c.preparation_steps AS descricao,
                c.image_url AS foto,
                em.display_order AS ordem
            FROM events e
            JOIN event_menus em ON e.id = em.event_id
            JOIN cocktails c ON em.cocktail_id = c.id
            WHERE e.custom_url_slug = %s
            ORDER BY em.display_order;
        """
        
        cur.execute(query, (url_slug,))
        cardapio = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Se não achar a festa, avisa o app
        if not cardapio:
            raise HTTPException(status_code=404, detail="Ops! Cardápio não encontrado.")
            
        # Formatando a resposta bonitinha para o App
        resposta = {
            "festa": cardapio[0]["nome_da_festa"],
            "data": cardapio[0]["data_da_festa"],
            "quantidade_drinks": len(cardapio),
            "drinks": cardapio
        }
        
        return resposta
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        
        
# # ==========================================
# # NOSSA TERCEIRA ROTA: CRIAR UM NOVO EVENTO
# # ==========================================
# @app.post("/events/")
# def criar_evento(evento: NovoEvento):
#     conn = get_db_connection()
#     if not conn:
#         raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
#     try:
#         cur = conn.cursor()
        
#         # O Python gera um UUID novinho para essa festa
#         novo_event_id = str(uuid.uuid4())
        
#         # O comando de inserção (usando %s para segurança contra hackers)
#         query = """
#             INSERT INTO events (id, account_id, event_name, event_date, custom_url_slug, status)
#             VALUES (%s, %s, %s, %s, %s, %s)
#             RETURNING id;
#         """
        
#         # A tupla com os valores exatos que vieram do aplicativo
#         valores = (
#             novo_event_id, 
#             evento.account_id, 
#             evento.event_name, 
#             evento.event_date, 
#             evento.custom_url_slug, 
#             evento.status
#         )
        
#         cur.execute(query, valores)
        
#         # O COMANDO MÁGICO: No INSERT, precisamos dar "Commit" para salvar de verdade!
#         conn.commit()
        
#         cur.close()
#         conn.close()
        
#         # Devolvemos uma resposta de sucesso para o aplicativo
#         return {
#             "status": "sucesso", 
#             "mensagem": "Festa criada com sucesso!", 
#             "event_id": novo_event_id,
#             "link_do_cardapio": f"aurorabartenders.com/{evento.custom_url_slug}"
#         }
        
#     except Exception as e:
#         # Se der qualquer erro (ex: slug duplicado), desfazemos a operação
#         conn.rollback() 
#         conn.close()
#         raise HTTPException(status_code=400, detail=str(e))
        
        
# ==========================================
# CARREGAR ESTOQUE DO CAMINHÃO (BLINDADO)
# ==========================================
@app.post("/inventory/load-event")
def carregar_estoque_evento(payload: CargaEventoBody = Body(...)): # 🛑 Usa o molde explícito aqui
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")

    try:
        cur = conn.cursor()
        
        # ==========================================
        # 1. CHECAGEM PRÉ-VOO (VALIDAÇÃO DE SALDO)
        # ==========================================
        erros_estoque = []
        
        for item in payload.itens:
            cur.execute("SELECT name, current_stock FROM ingredients WHERE id = %s", (item.ingredient_id,))
            resultado = cur.fetchone()
            
            if not resultado:
                erros_estoque.append({"insumo": f"ID {item.ingredient_id}", "pedido": item.quantity, "disponivel": 0})
                continue
                
            nome_insumo = resultado[0]
            estoque_atual = float(resultado[1] or 0)
            qtd_solicitada = float(item.quantity)
            
            if qtd_solicitada > estoque_atual:
                erros_estoque.append({
                    "insumo": nome_insumo,
                    "pedido": qtd_solicitada,
                    "disponivel": estoque_atual
                })
        
        if erros_estoque:
            raise HTTPException(status_code=400, detail=erros_estoque)

        # ==========================================
        # 2. SE PASSOU NO TESTE, FAZ A TRANSFERÊNCIA
        # ==========================================
        for item in payload.itens:
            # Tira do Galpão Principal
            cur.execute("UPDATE ingredients SET current_stock = current_stock - %s WHERE id = %s", 
                        (item.quantity, item.ingredient_id))
            
            # O MOTOBOY DO DESESPERO (A Regra do UPSERT)
            # Se a linha já existir (caminhão já foi), ele apenas SOMA a nova quantidade.
            query_upsert = """
                INSERT INTO event_stocks (event_id, ingredient_id, quantity_sent)
                VALUES (%s, %s, %s)
                ON CONFLICT (event_id, ingredient_id) 
                DO UPDATE SET quantity_sent = event_stocks.quantity_sent + EXCLUDED.quantity_sent;
            """
            cur.execute(query_upsert, (payload.event_id, item.ingredient_id, item.quantity))
        
        conn.commit() 
        return {"status": "sucesso", "detalhes": f"{len(payload.itens)} insumos carregados."}
        
    except HTTPException as he:
        if conn: conn.rollback()
        raise he 
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
    finally:
        if conn:
            cur.close()
            conn.close()

# ==========================================
# O "MOLDE" DE SUGESTÃO DE CARGA
# ==========================================
@app.get("/inventory/suggest-load/{event_id}")
def sugerir_carga(event_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    cur = conn.cursor()
    try:
        # A query agora usa COALESCE em tudo que é número para evitar o Erro 500
        query = """
            SELECT 
                i.id, 
                i.name,
                SUM(COALESCE(ci.quantity, 0) * COALESCE(em.planned_quantity, 0)) as total,
                i.measurement_unit
            FROM event_menus em
            JOIN cocktail_ingredients ci ON em.cocktail_id = ci.cocktail_id
            JOIN ingredients i ON ci.ingredient_id = i.id
            WHERE em.event_id = %s::uuid
            GROUP BY i.id, i.name, i.measurement_unit
        """
        # O ::uuid ali em cima força o banco a reconhecer o ID corretamente
        
        cur.execute(query, (event_id,))
        sugestoes = cur.fetchall()
        
        # Transformamos o resultado em uma lista limpa
        lista_final = []
        for s in sugestoes:
            lista_final.append({
                "id": str(s[0]), 
                "nome": s[1], 
                "sugerido": float(s[2]) if s[2] else 0.0, 
                "unidade": s[3]
            })
        
        return lista_final

    except Exception as e:
        # Esse print vai aparecer nos logs do seu Render!
        print(f"DEBUG LOGÍSTICA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro no cálculo: {str(e)}")
    finally:
        cur.close()
        conn.close()


# ==========================================
# NOSSA QUARTA ROTA: SALVAR O CARDÁPIO DA FESTA
# ==========================================
@app.post("/events/{event_id}/menu")
def salvar_cardapio(event_id: str, menu: NovoMenu):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        cur = conn.cursor()
        
        # 1. Primeiro, removemos apenas os drinks que NÃO estão na nova lista enviada
        # (Isso permite que você remova drinks do evento sem zerar os outros)
        if menu.drinks:
            placeholder = ', '.join(['%s'] * len(menu.drinks))
            query_delete = f"DELETE FROM event_menus WHERE event_id = %s AND cocktail_id NOT IN ({placeholder})"
            cur.execute(query_delete, [event_id] + menu.drinks)
        else:
            cur.execute("DELETE FROM event_menus WHERE event_id = %s", (event_id,))

        # 2. Inserimos os novos e ATUALIZAMOS a ordem dos que já existem
        # Nota: Para isso funcionar, sua tabela event_menus precisa de uma constraint UNIQUE(event_id, cocktail_id)

        query_upsert = """
            INSERT INTO event_menus (event_id, cocktail_id, display_order)
            VALUES (%s, %s, %s)
            ON CONFLICT (event_id, cocktail_id) 
            DO UPDATE SET display_order = EXCLUDED.display_order;
        """
        
        for posicao, drink_id in enumerate(menu.drinks, start=1):
            cur.execute(query_upsert, (event_id, drink_id, posicao))
            
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Cardápio atualizado preservando quantidades!"}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
        
# ==========================================
# ROTA: BUSCAR O CARDÁPIO DO EVENTO (PARA O ADMIN)
# Resolve o erro "undefined (reading 'forEach')"
# ==========================================
@app.get("/admin/events/{event_id}/menu")
def obter_menu_admin(event_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        # RealDictCursor garante que o Python devolva no formato JSON que o JS adora
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                c.id, 
                c.name AS drink_nome, 
                c.category AS categoria, 
                c.image_url, 
                c.sale_price AS preco_venda,
                em.display_order, 
                em.planned_quantity
            FROM event_menus em
            JOIN cocktails c ON em.cocktail_id = c.id
            WHERE em.event_id = %s
            ORDER BY em.display_order;
        """

        cur.execute(query, (event_id,))
        drinks_do_evento = cur.fetchall()
        
        # Devolvemos a lista direta para o forEach do JavaScript brilhar
        return {"status": "sucesso", "dados": drinks_do_evento}
        
    except Exception as e:
        print("Erro ao carregar menu admin:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


# ==========================================
# NOSSA QUINTA ROTA: CADASTRAR NOVO INSUMO
# ==========================================
@app.post("/ingredients/")
def criar_insumo(insumo: NovoInsumo):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        novo_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO ingredients (id, account_id, category_id, name, brand, measurement_unit, package_quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        valores = (novo_id, insumo.account_id, insumo.category_id, insumo.name, insumo.brand, insumo.measurement_unit, insumo.package_quantity)
        
        cur.execute(query, valores)
        conn.commit()
        
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Insumo cadastrado!", "ingredient_id": novo_id}
        
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# NOSSA SEXTA ROTA: REGISTRAR COMPRA E ATUALIZAR ESTOQUE
# ==========================================
@app.post("/purchases/")
def registrar_compra(compra: NovaCompra):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # 1. A API calcula o preço unitário (Matemática básica)
        unit_price = compra.total_paid / compra.packages_bought
        
        # 2. Salva o histórico financeiro na tabela de compras
        query_compra = """
            INSERT INTO ingredient_purchases (ingredient_id, packages_bought, total_paid, unit_price, supplier_name)
            VALUES (%s, %s, %s, %s, %s);
        """
        cur.execute(query_compra, (compra.ingredient_id, compra.packages_bought, compra.total_paid, unit_price, compra.supplier_name))
        
        # 3. A MÁGICA: Atualiza o custo e converte o estoque para a unidade base (ml/g)
        query_atualiza_estoque = """
            UPDATE ingredients
            SET current_cost_price = %s,
                -- CONVERSÃO AUTOMÁTICA: 3 garrafas * 1000ml = soma 3000ml no estoque!
                current_stock = current_stock + (%s * package_quantity)
            WHERE id = %s;
        """
        # Passamos os exatos mesmos parâmetros, o banco faz a matemática
        cur.execute(query_atualiza_estoque, (unit_price, compra.packages_bought, compra.ingredient_id))
        
        # Confirma as duas operações juntas (Se uma falhar, a outra é desfeita)
        conn.commit()
        
        cur.close()
        conn.close()
        return {
            "status": "sucesso", 
            "mensagem": f"Compra registrada! Estoque atualizado e novo custo unitário definido como R$ {unit_price:.2f}"
        }
        
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        
# ==========================================
# ROTA EXTRA 1: ZERAR ESTOQUE FÍSICO DO INSUMO
# ==========================================
@app.put("/ingredients/{ingredient_id}/zero")
def zerar_estoque(ingredient_id: str):
    conn = get_db_connection()
    if not conn: 
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        # O UPDATE perfeito: Zera apenas o saldo, mantendo o item no catálogo!
        query = "UPDATE ingredients SET current_stock = 0 WHERE id = %s"
        cur.execute(query, (ingredient_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "mensagem": "Estoque físico zerado com sucesso!"}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# ROTA EXTRA 2: EXCLUIR INSUMO (SOFT DELETE)
# ==========================================
@app.delete("/ingredients/{ingredient_id}")
def excluir_insumo_definitivo(ingredient_id: str):
    conn = get_db_connection()
    if not conn: 
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # O GOLPE DE MESTRE: Em vez de DELETE, nós fazemos um UPDATE
        # O item some da tela, mas as compras dele continuam intactas no banco!
        query_insumo = "UPDATE ingredients SET is_active = FALSE WHERE id = %s"
        cur.execute(query_insumo, (ingredient_id,))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Insumo não encontrado no banco.")
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "mensagem": "Insumo arquivado com sucesso! O histórico financeiro foi mantido."}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# ROTA EXTRA 3: ATUALIZAR INSUMO EXISTENTE
# ==========================================
@app.put("/ingredients/{ingredient_id}")
def editar_insumo(ingredient_id: str, payload: EdicaoInsumo):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")

    try:
        cur = conn.cursor()

# 1. Tenta achar o ID do Tipo de Insumo
        cur.execute("SELECT id FROM ingredient_types WHERE name = %s", (payload.type_name,))
        tipo_row = cur.fetchone()
        
        if not tipo_row:
            cur.execute("INSERT INTO ingredient_types (name) VALUES (%s) RETURNING id", (payload.type_name,))
            type_id = cur.fetchone()[0]  # <-- CORREÇÃO: Pegamos a posição 0 da resposta
        else:
            type_id = tipo_row[0]        # <-- CORREÇÃO: Pegamos a posição 0 da resposta

        # 2. Atualiza o Insumo de fato
        query = """
            UPDATE ingredients
            SET name = %s, brand = %s, type_id = %s, measurement_unit = %s,
                package_quantity = %s, current_cost_price = %s
            WHERE id = %s
        """
        cur.execute(query, (
            payload.name, payload.brand, type_id, payload.measurement_unit,
            payload.package_quantity, payload.current_cost_price, ingredient_id
        ))

        conn.commit()
        cur.close()
        conn.close()

        return {"status": "sucesso", "mensagem": "Insumo atualizado!"}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# ROTA: LISTAR TIPOS DE INSUMOS (CORRIGIDA)
# ==========================================
@app.get("/ingredient-types/")
def listar_tipos_insumos():
    conn = get_db_connection()
    if not conn: 
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM ingredient_types ORDER BY name")
        tipos = cur.fetchall()
        cur.close()
        conn.close()
        
        # A CORREÇÃO: Pegamos as posições exatas da tupla [0] e [1]
        # e montamos o formato bonitinho que o Javascript consegue ler
        dados_formatados = [{"id": str(t[0]), "name": t[1]} for t in tipos]
        
        return {"status": "sucesso", "dados": dados_formatados}
        
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA MESTRA: REGISTRAR VENDA (PDV)
# ==========================================
@app.post("/sales/")
def registrar_venda(payload: NovaVenda):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")

    try:
        cur = conn.cursor() 
        
        # PASSO 1: Busca a receita e os custos (Removido o current_stock global que não usaremos)
        query_receita = """
            SELECT 
                ci.ingredient_id, 
                ci.quantity AS qtd_necessaria,
                i.current_cost_price,
                i.package_quantity
            FROM cocktail_ingredients ci
            JOIN ingredients i ON ci.ingredient_id = i.id
            WHERE ci.cocktail_id = %s AND i.is_active = TRUE
        """
        cur.execute(query_receita, (payload.cocktail_id,))
        ingredientes_receita = cur.fetchall()

        if not ingredientes_receita:
            raise HTTPException(status_code=400, detail="Ficha técnica vazia ou insumos inativos.")

        custo_total_drink = 0.0

        # ==========================================
        # NOVO PASSO 2: BAIXA DE ESTOQUE POR EVENTO
        # ==========================================
        for ing in ingredientes_receita:
            id_insumo = ing[0]
            qtd_necessaria = float(ing[1])
            custo_garrafa = float(ing[2]) if ing[2] else 0.0 # Índice 2: Custo
            tamanho_emb = float(ing[3]) if ing[3] and ing[3] > 0 else 1.0 # Índice 3: Embalagem
            
            # Cálculo do Frozen Cost
            custo_por_unidade = custo_garrafa / tamanho_emb
            custo_total_drink += (custo_por_unidade * qtd_necessaria)

            # Baixa no estoque do evento
            query_baixa_evento = """
                UPDATE event_stocks 
                SET quantity_used = quantity_used + %s 
                WHERE event_id = %s AND ingredient_id = %s
            """
            cur.execute(query_baixa_evento, (qtd_necessaria, payload.event_id, id_insumo))
            
            if cur.rowcount == 0:
                raise Exception(f"Insumo ID {id_insumo} não foi alocado para este evento.")

        # PASSO 3: Salva a venda
        query_venda = """
            INSERT INTO sales (event_id, cocktail_id, price, frozen_cost, user_name)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        cur.execute(query_venda, (payload.event_id, payload.cocktail_id, payload.price, custo_total_drink, payload.user_name))
        
        venda_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        return {
            "status": "sucesso", 
            "venda_id": str(venda_id), 
            "frozen_cost": round(custo_total_drink, 2)
        }

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# ROTA MESTRA 2: ESTORNAR VENDA E DEVOLVER ESTOQUE
# ==========================================

@app.post("/sales/cancel")
def estornar_venda(payload: EstornoVenda):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Busca o cocktail_id dessa venda para saber o que devolver ao estoque
        cur.execute("SELECT cocktail_id FROM sales WHERE id = %s", (payload.sale_id,))
        venda = cur.fetchone()
        if not venda:
            raise Exception("Venda não encontrada.")
        
        cocktail_id = venda[0]

        # 2. Busca os ingredientes daquele drink
        cur.execute("SELECT ingredient_id, quantity FROM cocktail_ingredients WHERE cocktail_id = %s", (cocktail_id,))
        ingredientes = cur.fetchall()

        # 3. Devolve para o quantity_used do evento
        for ing in ingredientes:
            cur.execute("""
                UPDATE event_stocks 
                SET quantity_used = quantity_used - %s 
                WHERE event_id = %s::uuid AND ingredient_id = %s
            """, (float(ing[1]), payload.event_id, ing[0]))

        # 4. Deleta a venda
        cur.execute("DELETE FROM sales WHERE id = %s", (payload.sale_id,))
        
        conn.commit()
        return {"status": "sucesso"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# ==========================================
# ROTA: RESGATE DE HISTÓRICO (ANTI-F5)
# ==========================================
@app.get("/sales/event/{event_id}")
def listar_vendas_evento(event_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
        
    try:
        cur = conn.cursor()
        
        # Busca as vendas do evento ordenadas das mais antigas para as mais novas
        # Assim o frontend reconstrói a tela exatamente na ordem que as coisas aconteceram
        query = """
            SELECT id, cocktail_id, price, user_name
            FROM sales 
            WHERE event_id = %s
            ORDER BY id ASC
        """
        cur.execute(query, (event_id,))
        vendas = cur.fetchall()
        
        resultado = []
        for v in vendas:
            resultado.append({
                "id": str(v[0]),
                "cocktail_id": str(v[1]),
                "price": float(v[2]) if v[2] else 0.0,
                "user_name": str(v[3]) if v[3] else "Desconhecido"
            })
            
        cur.close()
        conn.close()
        
        return resultado
        
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# NOSSA SÉTIMA ROTA: PAINEL DE ESTOQUE (INVENTORY)
# ==========================================
@app.get("/inventory/{account_id}")
def relatorio_estoque(account_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # O SQL que faz toda a matemática financeira em tempo real
        # Usamos NULLIF para evitar o erro de "divisão por zero" caso alguma embalagem esteja zerada
        query = """
            SELECT 
                i.id,
                i.name AS insumo,
                i.brand AS marca,             
                it.name AS tipo,  
                i.current_stock AS estoque_ml_g,
                i.measurement_unit AS unidade,
                i.current_cost_price AS custo_ultima_embalagem,
                i.package_quantity AS tamanho_embalagem,  
                ROUND((i.current_stock / NULLIF(i.package_quantity, 0)), 2) AS qtd_embalagens_estoque,
                ROUND((i.current_stock / NULLIF(i.package_quantity, 0)) * i.current_cost_price, 2) AS dinheiro_parado
            FROM ingredients i
            LEFT JOIN ingredient_types it ON i.type_id = it.id
            -- A MÁGICA AQUI: Só trazemos os ativos!
            WHERE i.account_id = %s AND i.is_active = TRUE
            ORDER BY it.name, i.name;
        """
        
        cur.execute(query, (account_id,))
        estoque = cur.fetchall()
        
        # O Python soma todo o dinheiro parado no estoque inteiro de uma vez
        total_geral = sum((item['dinheiro_parado'] or 0) for item in estoque)
        
        cur.close()
        conn.close()
        
        # Devolvemos o JSON perfeito para montar a tela do App
        return {
            "status": "sucesso",
            "total_de_insumos": len(estoque),
            "capital_total_imobilizado": round(total_geral, 2),
            "dados": estoque
        }
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        

# ==========================================
# NOSSA OITAVA ROTA: CRIAR DRINK COM FICHA TÉCNICA (POST)
# ==========================================
@app.post("/cocktails/")
def criar_drink_completo(drink: NovoCocktail):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        novo_drink_id = str(uuid.uuid4())
        
        # Inserimos o Cabeçalho (AGORA COM O MIN_PACKAGE_LEVEL)
        query_drink = """
            INSERT INTO cocktails (id, account_id, name, preparation_steps, category, technique, drink_type, sale_price, image_url, min_package_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(query_drink, (
            novo_drink_id, drink.account_id, drink.name, 
            drink.preparation_steps, drink.category, drink.technique, 
            drink.drink_type, drink.sale_price, drink.image_url, 
            drink.min_package_level # <-- Variável nova aqui no final
        ))
        
        # Loop da Ficha Técnica
        query_receita = """
            INSERT INTO cocktail_ingredients (cocktail_id, ingredient_id, quantity)
            VALUES (%s, %s, %s);
        """
        for item in drink.recipe:
            cur.execute(query_receita, (novo_drink_id, item.ingredient_id, item.quantity))
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "mensagem": f"Drink '{drink.name}' criado com sucesso!",
            "drink_id": novo_drink_id
        }
        
    except Exception as e:
        conn.rollback() 
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA NOVA: ATUALIZAR DRINK EXISTENTE (PUT)
# ==========================================
@app.put("/cocktails/{cocktail_id}")
def atualizar_drink_completo(cocktail_id: str, drink: NovoCocktail):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
   # 1. Atualiza o Cabeçalho do drink (COM MIN_PACKAGE_LEVEL)
        query_drink = """
            UPDATE cocktails 
            SET name = %s, preparation_steps = %s, category = %s, technique = %s, 
                drink_type = %s, sale_price = %s, image_url = %s, min_package_level = %s
            WHERE id = %s AND account_id = %s;
        """
        cur.execute(query_drink, (
            drink.name, drink.preparation_steps, drink.category, drink.technique, 
            drink.drink_type, drink.sale_price, drink.image_url, 
            drink.min_package_level, # <-- Variável nova adicionada aqui
            cocktail_id, drink.account_id
        ))
        
        # 2. Apaga a receita antiga inteira (é mais seguro que tentar adivinhar o que mudou)
        cur.execute("DELETE FROM cocktail_ingredients WHERE cocktail_id = %s;", (cocktail_id,))
        
        # 3. Insere a receita nova e atualizada
        query_receita = """
            INSERT INTO cocktail_ingredients (cocktail_id, ingredient_id, quantity)
            VALUES (%s, %s, %s);
        """
        for item in drink.recipe:
            cur.execute(query_receita, (cocktail_id, item.ingredient_id, item.quantity))
            
        # 4. Confirma a transação
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "mensagem": f"Drink '{drink.name}' atualizado perfeitamente!"
        }
        
    except Exception as e:
        conn.rollback() 
        conn.close()
        # Se for erro de nome duplicado, repassamos de forma legível
        if "unique_drink_name" in str(e):
            raise HTTPException(status_code=400, detail="unique_drink_name")
        raise HTTPException(status_code=400, detail=str(e))
        
# ==========================================
# NOSSA NONA ROTA: LISTAR CATÁLOGO MESTRE DE DRINKS
# ==========================================
@app.get("/drinks/{account_id}")
def listar_todos_drinks(account_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Busca todos os drinks da sua conta, renomeando as colunas para o JS entender
        query = """
            SELECT 
                id, 
                name AS drink_nome, 
                sale_price AS preco_venda, 
                image_url,
                technique,
                drink_type,
                category,
                preparation_steps, 
                min_package_level
            FROM cocktails 
            WHERE account_id = %s
            ORDER BY name;
        """
        
        cur.execute(query, (account_id,))
        drinks_catalogo = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "quantidade": len(drinks_catalogo), 
            "dados": drinks_catalogo
        }
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        
# ==========================================
# NOSSA DÉCIMA ROTA: LISTAR O CARDÁPIO E O ESTOQUE REAL
# ==========================================
@app.get("/events/{event_id}/menu") 
def listar_menu_evento(event_id: str): 
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor) 
    
    try:
        # 1. TRADUTOR: Acha a festa e pega o ID e o Nome dela!
        cur.execute("""
            SELECT id, name FROM events 
            WHERE custom_url_slug = %s OR id::text = %s
        """, (event_id, event_id))
        
        evento = cur.fetchone()
        if not evento:
            raise HTTPException(status_code=404, detail="Festa não encontrada.")

        id_verdadeiro = evento['id']
        nome_da_festa = evento['name']

        # 2. O MOTOR BI DE ESTOQUE (Calcula a capacidade real de cada drink)
        cur.execute("""
            SELECT 
                c.id, 
                c.name AS drink_nome, 
                c.sale_price AS preco_venda, 
                c.image_url,
                (
                    SELECT STRING_AGG(i.name, ', ') 
                    FROM cocktail_ingredients ci 
                    JOIN ingredients i ON ci.ingredient_id = i.id
                    WHERE ci.cocktail_id = c.id
                ) AS descricao,
                
                -- =========================================================
                -- A MÁGICA DA COQUETELARIA: O Cálculo do Insumo Gargalo!
                -- Pega o (Enviado - Usado) e divide pela receita do drink.
                -- =========================================================
                COALESCE(
                    (
                        SELECT MIN(
                            FLOOR(
                                (COALESCE(es.quantity_sent, 0) - COALESCE(es.quantity_used, 0)) / NULLIF(ci.quantity, 0)
                            )
                        )
                        FROM cocktail_ingredients ci
                        LEFT JOIN event_stocks es ON ci.ingredient_id = es.ingredient_id AND es.event_id = em.event_id
                        WHERE ci.cocktail_id = c.id
                    ),
                    em.planned_quantity -- Fallback de segurança se o drink não tiver ficha técnica
                ) AS planned_quantity

            FROM event_menus em
            JOIN cocktails c ON em.cocktail_id = c.id
            WHERE em.event_id = %s
            ORDER BY em.display_order;
        """, (id_verdadeiro,))
        
        drinks = cur.fetchall()
        
        # 3. Empacota e envia pro celular!
        return {
            "festa": nome_da_festa,
            "drinks": drinks
        }

    except Exception as e:
        print(f"Erro na rota de menu: {e}") 
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    
# ==========================================
# NOSSA DÉCIMA PRIMEIRA ROTA: BUSCAR RECEITA (AGORA INTELIGENTE POR PACOTE)
# ==========================================
@app.get("/cocktails/{cocktail_id}/recipe")
def ver_receita(cocktail_id: str, pacote: str = None, account_id: str = None):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Busca os textos de preparo
        cur.execute("SELECT technique, preparation_steps FROM cocktails WHERE id = %s;", (cocktail_id,))
        drink_info = cur.fetchone()
        
        # 2. Busca os ingredientes aplicando a substituição de marcas se o pacote for informado
        query_ingredientes = """
            SELECT 
                i.id AS ingrediente_id, 
                COALESCE(real_ing.name, i.name) AS ingrediente, 
                COALESCE(real_ing.brand, i.brand) AS marca,
                ci.quantity AS quantidade, 
                i.measurement_unit AS unidade,
                
                -- Matemática dinâmica: se houver regra para o pacote, calcula o preço da marca real
                ((COALESCE(real_ing.current_cost_price, i.current_cost_price)::NUMERIC / 
                  COALESCE(NULLIF(COALESCE(real_ing.package_quantity, i.package_quantity)::NUMERIC, 0), 1)) * ci.quantity::NUMERIC) AS custo
                
            FROM cocktail_ingredients ci
            JOIN ingredients i ON ci.ingredient_id = i.id
            
            -- Se 'pacote' e 'account_id' forem enviados, o JOIN abaixo vai encontrar a regra de substituição
            LEFT JOIN package_rules pr 
                ON pr.categoria_generica = i.name 
                AND pr.pacote = %s 
                AND pr.account_id = %s
            LEFT JOIN ingredients real_ing ON pr.real_ingredient_id = real_ing.id
            
            WHERE ci.cocktail_id = %s
            ORDER BY i.name;
        """
        
        # Passamos os parâmetros para o SQL. Se forem None, o LEFT JOIN simplesmente não trará nada (o que é perfeito)
        cur.execute(query_ingredientes, (pacote, account_id, cocktail_id))
        ingredientes = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "drink": drink_info,
            "ingredientes": ingredientes
        }
        
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
# ==========================================
# NOSSA DÉCIMA SEGUNDA ROTA: REGISTRAR VENDA (AGORA COM AUDITORIA DE USUÁRIO)
# ==========================================
# Adicionamos o user_name na url/query
@app.post("/events/{event_id}/sell/{cocktail_id}")
def registrar_venda_direta(event_id: str, cocktail_id: str, user_name: str = "Desconhecido"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT ingredient_id, quantity FROM cocktail_ingredients WHERE cocktail_id = %s;", (cocktail_id,))
        receita = cur.fetchall()
        
        cur.execute("SELECT sale_price FROM cocktails WHERE id = %s;", (cocktail_id,))
        drink_info = cur.fetchone()
        preco_venda = drink_info['sale_price'] if drink_info and 'sale_price' in drink_info else 0

        for item in receita:
            cur.execute("""
                UPDATE ingredients SET current_stock = current_stock - %s WHERE id = %s;
            """, (item['quantity'], item['ingredient_id']))
            
        # 4. Grava no Livro Caixa INCLUINDO o nome do bartender
        cur.execute("""
            INSERT INTO sales (event_id, cocktail_id, price, user_name)
            VALUES (%s, %s, %s, %s);
        """, (event_id, cocktail_id, preco_venda, user_name))
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "mensagem": "Venda registrada com auditoria!"}
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# NOSSA DÉCIMA TERCEIRA ROTA: REGISTRAR ESTORNO (DEVOLVE ESTOQUE + CANCELA CAIXA)
# ==========================================
@app.post("/events/{event_id}/cancel/{cocktail_id}")
def registrar_estorno(event_id: str, cocktail_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Busca a receita
        cur.execute("SELECT ingredient_id, quantity FROM cocktail_ingredients WHERE cocktail_id = %s;", (cocktail_id,))
        receita = cur.fetchall()
        
        # 2. Devolve para o estoque físico
        for item in receita:
            cur.execute("""
                UPDATE ingredients SET current_stock = current_stock + %s WHERE id = %s;
            """, (item['quantity'], item['ingredient_id']))
            
        # 3. Rasga o recibo (Apaga a ÚLTIMA venda deste drink neste evento)
        cur.execute("""
            DELETE FROM sales 
            WHERE id = (
                SELECT id FROM sales 
                WHERE event_id = %s AND cocktail_id = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            );
        """, (event_id, cocktail_id))
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "mensagem": "Estorno completo: Estoque e Caixa revertidos!"}
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
   
# ==========================================
# MÓDULO DE EQUIPE (STAFF) - MULTI-TENANT
# ==========================================

# 1. ROTA DE LOGIN DO FREELANCER (KDS)
@app.get("/login/{phone}")
def login_staff(phone: str, account_id: str): 
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id é obrigatório para login")

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, role 
            FROM staff 
            WHERE phone = %s AND account_id = %s AND status = 'ativo';
        """, (phone, account_id))
        
        user = cur.fetchone()
        
        if user:
            return {"status": "sucesso", "usuario": user}
        else:
            raise HTTPException(status_code=404, detail="Telefone não encontrado nesta agência ou inativo")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()

# 2. ROTA PARA LISTAR A EQUIPE (Admin)
@app.get("/team")
@app.get("/staff") # Aceita os dois nomes
def listar_equipe(account_id: str):
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id é obrigatório")
        
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Trazendo a equipe com os campos novos!
        cur.execute("""
            SELECT id, name, role, phone, status, cpf, 
                   TO_CHAR(birth_date, 'YYYY-MM-DD') as birth_date, 
                   gender, base_fee, additional_fee 
            FROM staff 
            WHERE account_id = %s AND status = 'ativo'
            ORDER BY name ASC
        """, (account_id,))
        
        return cur.fetchall() 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()

# 3. ROTA PARA ADICIONAR NOVO MEMBRO (Admin)
@app.post("/team")
def adicionar_membro(membro: NovoMembro):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # VERIFICAÇÃO DE CPF DUPLICADO (Com cast ::uuid para evitar erro 500 do Postgres)
        if membro.cpf and membro.cpf.strip() != "":
            cur.execute("SELECT id FROM staff WHERE cpf = %s AND account_id = %s::uuid", (membro.cpf, membro.account_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Este CPF já está cadastrado para outro membro na sua agência.")

        dt_nasc = None if not membro.birth_date or membro.birth_date.strip() == "" else membro.birth_date
        
        cur.execute("""
            INSERT INTO staff (account_id, name, phone, role, status, cpf, birth_date, gender, base_fee, additional_fee)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (membro.account_id, membro.name, membro.phone, membro.role, membro.status, 
              membro.cpf, dt_nasc, membro.gender, membro.base_fee, membro.additional_fee))
        
        novo_id = cur.fetchone()['id']
        conn.commit()
        return {"status": "sucesso", "id": novo_id}
    except HTTPException as he:
        if conn: conn.rollback()
        raise he 
    except Exception as e:
        if conn: conn.rollback()
        print(f"ERRO NO POST /team: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no banco de dados: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

# 4. ROTA PARA ATUALIZAR (EDITAR) MEMBRO (Admin)
@app.put("/team/{membro_id}")
def atualizar_membro(membro_id: int, membro: EditaMembro):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # VERIFICAÇÃO DE CPF DUPLICADO (Com cast explícito ::uuid)
        if membro.cpf and membro.cpf.strip() != "":
            cur.execute("SELECT id FROM staff WHERE cpf = %s AND account_id = %s::uuid AND id != %s", (membro.cpf, membro.account_id, membro_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Este CPF já pertence a outro membro da equipe.")

        dt_nasc = None if not membro.birth_date or membro.birth_date.strip() == "" else membro.birth_date
        
        cur.execute("""
            UPDATE staff 
            SET name = %s, phone = %s, role = %s, cpf = %s, 
                birth_date = %s, gender = %s, base_fee = %s, additional_fee = %s
            WHERE id = %s AND account_id = %s::uuid
        """, (membro.name, membro.phone, membro.role, membro.cpf, dt_nasc, 
              membro.gender, membro.base_fee, membro.additional_fee, membro_id, membro.account_id))
        
        conn.commit()
        return {"status": "sucesso"}
    except HTTPException as he:
        if conn: conn.rollback()
        raise he 
    except Exception as e:
        if conn: conn.rollback()
        print(f"ERRO NO PUT /team: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no banco de dados: {str(e)}")
    finally:
        if conn: conn.close()

# 5. ROTA PARA EXCLUIR (SOFT DELETE) (Admin)
@app.delete("/team/{membro_id}")
def deletar_membro(membro_id: int, account_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE staff 
            SET status = 'inativo'
            WHERE id = %s AND account_id = %s
        """, (membro_id, account_id))
        
        conn.commit()
        return {"status": "sucesso"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()
    
# ==========================================
# NOSSA DÉCIMA SEXTA ROTA: CRIAR NOVO EVENTO (ADMIN)
# ==========================================
@app.post("/events/new")
def create_event(event: EventCreate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # --- VERIFICAÇÃO DE DUPLICADOS ---
        check_query = "SELECT id FROM events WHERE name = %s AND event_date = %s"
        cur.execute(check_query, (event.nome, event.dataEvento))
        if cur.fetchone():
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Este evento já foi cadastrado!")

        # --- SE NÃO EXISTE, SEGUE O BAILE (AGORA COM ACCOUNT_ID) ---
        query = """
            INSERT INTO events (
                account_id, name, responsible_name, phone, event_date, start_time, 
                duration_h, duration_m, extra_h, extra_m, end_time, location
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
            RETURNING id;
        """
        cur.execute(query, (
            event.account_id, # <--- ADICIONADO AQUI!
            event.nome, event.responsavel, event.telefone, event.dataEvento, 
            event.horaEvento, event.durH, event.durM, event.extH, event.extM, 
            event.termino, event.local
        ))
        
        novo_id = str(cur.fetchone()['id'])
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "id": novo_id}
        
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
# ==========================================
# NOSSA DÉCIMA SÉTIMA ROTA: LISTAR EVENTOS (ADMIN)
# ==========================================
@app.get("/events")
def list_events(account_id: str): # 📍 AGORA EXIGE A IDENTIFICAÇÃO DA AGÊNCIA
    if not account_id:
        raise HTTPException(status_code=400, detail="O account_id é obrigatório para listar os eventos.")
        
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 📍 O MODO SAAS ATIVADO: Filtra estritamente pela agência (account_id)
        cur.execute("""
            SELECT * FROM events 
            WHERE account_id = %s 
            ORDER BY event_date DESC;
        """, (account_id,))
        
        eventos = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "eventos": eventos}
        
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
# ==========================================
# NOVOS MOLDES PARA AS AÇÕES DOS BOTÕES
# ==========================================

# 1. ROTA PARA MUDAR STATUS (Encerrar / Reabrir)
@app.patch("/events/{event_id}/status")
def mudar_status_evento(event_id: str, status_data: EventStatus):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    try:
        cur = conn.cursor()
        
        # A MÁGICA DE SINCRONIA AQUI:
        if status_data.status == 'aberto':
            # Se abriu o bar, garante que o evento seja is_active = TRUE
            cur.execute("UPDATE events SET status = %s, is_active = TRUE WHERE id = %s", (status_data.status, event_id))
        else:
            # Se o bar fechou ('fechado'), apenas trava o celular dos bartenders, 
            # mas deixa o evento is_active = TRUE para o gerente ver os relatórios amanhã!
            cur.execute("UPDATE events SET status = %s WHERE id = %s", (status_data.status, event_id))
            
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": f"Status alterado para {status_data.status}"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# 2. ROTA PARA ZERAR O EVENTO (Limpar Vendas/Pedidos do Caixa)
@app.post("/events/{event_id}/reset")
def zerar_evento(event_id: str):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    try:
        cur = conn.cursor()
        # Apaga todo o histórico de vendas/caixa atrelado a este evento
        cur.execute("DELETE FROM sales WHERE event_id = %s", (event_id,))
        # Se você tiver uma tabela de 'orders' (pedidos do KDS) no Postgres, descomente a linha abaixo:
        # cur.execute("DELETE FROM orders WHERE event_id = %s", (event_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Caixa e histórico do evento zerados!"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# 3. ROTA PARA EXCLUIR EVENTO PERMANENTEMENTE
@app.delete("/events/{event_id}")
def deletar_evento(event_id: str):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    try:
        cur = conn.cursor()
        # Apaga o evento (O PostgreSQL deve estar configurado com 'ON DELETE CASCADE' 
        # para apagar automaticamente o cardápio e as vendas vinculadas a ele)
        cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Evento excluído com sucesso!"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    

# ROTA PARA ATUALIZAR A QUANTIDADE DE UM DRINK NO EVENTO
@app.patch("/events/{event_id}/menu/{cocktail_id}/quantity")
def atualizar_quantidade_drink(event_id: str, cocktail_id: str, dados: EstoqueDrink):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        cur = conn.cursor()
        query = """
            UPDATE event_menus 
            SET planned_quantity = %s 
            WHERE event_id = %s AND cocktail_id = %s
        """
        cur.execute(query, (dados.quantidade, event_id, cocktail_id))
        conn.commit()
        
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Quantidade atualizada!"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
# ROTA PARA ATUALIZAR ESTOQUE EM MASSA
@app.post("/events/{event_id}/menu/bulk-quantity")
def atualizar_estoque_massa(event_id: str, dados: EstoqueDrink):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    try:
        cur = conn.cursor()
        # Atualiza a quantidade planejada de TODOS os drinks daquele evento
        query = "UPDATE event_menus SET planned_quantity = %s WHERE event_id = %s"
        cur.execute(query, (dados.quantidade, event_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": f"Estoque de todos os drinks alterado para {dados.quantidade}"}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# ROTA: GERAR LISTA DE COMPRAS (AGORA COM CUSTO REAL E DE AQUISIÇÃO)
# ==========================================
@app.get("/events/{event_id}/shopping-list")
def gerar_lista_compras(event_id: str):
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Erro de conexão")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                i.name AS insumo,
                i.brand AS marca,
                
                -- FORMATADOR DE NECESSIDADE
                CASE 
                    WHEN i.measurement_unit IN ('g', 'ml') AND SUM(COALESCE(em.planned_quantity, 0) * ci.quantity) >= 1000 THEN 
                        TO_CHAR(SUM(COALESCE(em.planned_quantity, 0) * ci.quantity) / 1000.0, 'FM999999990.00') || CASE WHEN i.measurement_unit = 'g' THEN ' Kg' ELSE ' L' END
                    ELSE 
                        SUM(COALESCE(em.planned_quantity, 0) * ci.quantity) || ' ' || i.measurement_unit
                END AS total_necessario_formatado,

                -- FORMATADOR DA EMBALAGEM
                CASE 
                    WHEN i.package_quantity IS NULL THEN '⚠️ Sem Cadastro'
                    WHEN i.measurement_unit IN ('g', 'ml') AND i.package_quantity >= 1000 THEN 
                        TO_CHAR(i.package_quantity / 1000.0, 'FM999999990.00') || CASE WHEN i.measurement_unit = 'g' THEN ' Kg' ELSE ' L' END
                    ELSE 
                        i.package_quantity || ' ' || i.measurement_unit
                END AS tamanho_embalagem,
                
                COALESCE(i.current_cost_price, 0) AS preco_unitario,
                
                -- 1. CUSTO REAL/PROPORCIONAL
                ROUND(
                    (SUM(COALESCE(em.planned_quantity, 0) * ci.quantity)::numeric / 
                    NULLIF(COALESCE(i.package_quantity, 1), 0)::numeric) * COALESCE(i.current_cost_price, 0)::numeric, 2
                ) AS custo_real_uso,

                -- 2. QUANTIDADE DE PACOTES (COMPRA)
                CEIL(
                    SUM(COALESCE(em.planned_quantity, 0) * ci.quantity)::numeric / 
                    NULLIF(COALESCE(i.package_quantity, 1), 0)::numeric
                ) AS qtd_comprar,
                
                -- 3. CUSTO DE AQUISIÇÃO
                (
                    CEIL(
                        SUM(COALESCE(em.planned_quantity, 0) * ci.quantity)::numeric / 
                        NULLIF(COALESCE(i.package_quantity, 1), 0)::numeric
                    ) * COALESCE(i.current_cost_price, 0)::numeric
                ) AS custo_aquisicao
                
            FROM event_menus em
            JOIN cocktail_ingredients ci ON em.cocktail_id = ci.cocktail_id
            JOIN ingredients i ON ci.ingredient_id = i.id
            WHERE em.event_id = %s
            GROUP BY i.id, i.name, i.brand, i.measurement_unit, i.package_quantity, i.current_cost_price
            HAVING SUM(COALESCE(em.planned_quantity, 0) * ci.quantity) > 0
            ORDER BY i.name;
        """
        
        cur.execute(query, (event_id,))
        lista = cur.fetchall()
        
        # O Python agora soma os dois fluxos financeiros de forma segura
        total_desembolso = sum(float(item['custo_aquisicao'] or 0) for item in lista)
        total_real = sum(float(item['custo_real_uso'] or 0) for item in lista)
        
        cur.close()
        conn.close()
        
        # Devolvemos a estrutura completa para o seu admin.html ler!
        return {
            "status": "sucesso", 
            "total_estimado": round(total_desembolso, 2),
            "total_custo_real": round(total_real, 2),
            "lista": lista
        }
    except Exception as e:
        if conn: conn.close()
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# RADAR DO GESTOR: STATUS DOS INSUMOS DO EVENTO
# ==========================================
@app.get("/events/{event_id}/inventory-status")
def status_estoque_evento(event_id: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                i.name AS insumo,
                i.measurement_unit AS unidade,
                COALESCE(es.quantity_sent, 0) AS enviado,
                COALESCE(es.quantity_used, 0) AS usado,
                (COALESCE(es.quantity_sent, 0) - COALESCE(es.quantity_used, 0)) AS saldo
            FROM event_stocks es
            JOIN ingredients i ON es.ingredient_id = i.id
            WHERE es.event_id = %s
            ORDER BY saldo ASC; -- Traz os menores saldos primeiro!
        """, (event_id,))
        
        status_insumos = cur.fetchall()
        return {"status": "sucesso", "insumos": status_insumos}

    except Exception as e:
        print(f"Erro no radar do gestor: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# ==========================================
# ROTA: CRIAR PEDIDO (KDS)
# ==========================================
@app.post("/orders/create")
def criar_pedido(payload: dict):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. TRADUTOR: Descobre o ID verdadeiro da festa (mesmo que chegue "Festa-Teste")
        identificador = payload['event_id']
        cur.execute("""
            SELECT id FROM events 
            WHERE custom_url_slug = %s OR id::text = %s
        """, (identificador, identificador))
        evento = cur.fetchone()
        if not evento:
            raise Exception("Festa não encontrada.")
        
        id_verdadeiro = evento[0]

        # 2. REGRA DE OURO (Agora checando pelo ID do celular, muito mais seguro!)
        client_id = payload.get('client_id')
        client_name = payload.get('client_name')

        cur.execute("""
            SELECT SUM(quantity) FROM event_order_items oi
            JOIN event_orders o ON oi.order_id = o.id
            WHERE o.client_id = %s AND o.status IN ('Pendente', 'Preparando', 'Pronto')
            AND o.event_id = %s
        """, (client_id, id_verdadeiro))
        
        total_ativo = cur.fetchone()[0] or 0
        novos_itens = sum(item['qty'] for item in payload['items'])

        if (total_ativo + novos_itens) > 2:
            raise Exception("Limite de 2 drinks por vez atingido! Aguarde a entrega.")

        # 3. Cria o Pedido (Caixa Forte) - Inserindo o client_id e usando id_verdadeiro!
        cur.execute("""
            INSERT INTO event_orders (event_id, client_name, client_id, status) 
            VALUES (%s, %s, %s, 'Pendente') RETURNING id
        """, (id_verdadeiro, client_name, client_id))
        order_id = cur.fetchone()[0]

        # 4. Insere os Itens
        for item in payload['items']:
            cur.execute("INSERT INTO event_order_items (order_id, cocktail_id, quantity) VALUES (%s, %s, %s)",
                        (order_id, item['id'], item['qty']))
        
        conn.commit()
        return {"status": "sucesso", "order_id": order_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# ==========================================
# ROTA: FINALIZAR PEDIDO (KDS)
# ==========================================
@app.post("/orders/{order_id}/finalize")
def finalizar_pedido_e_baixar_estoque(order_id: str, payload: dict):
    # payload: { "bartender": "Ricardo" }
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Busca os itens do pedido e o ID do evento
        cur.execute("""
            SELECT o.event_id, oi.cocktail_id, oi.quantity, o.client_name 
            FROM event_orders o
            JOIN event_order_items oi ON o.id = oi.order_id
            WHERE o.id = %s AND o.status != 'Entregue'
        """, (order_id,))
        itens = cur.fetchall()
        
        if not itens:
            raise Exception("Pedido não encontrado ou já finalizado.")

        event_id = itens[0][0]
        client_name = itens[0][3]

        for event_id, cocktail_id, qtd, client in itens:
            # 2. Busca a Ficha Técnica do Drink (Ingredientes e ML)
            cur.execute("""
                SELECT ingredient_id, quantity 
                FROM cocktail_ingredients 
                WHERE cocktail_id = %s
            """, (cocktail_id,))
            ingredientes = cur.fetchall()

            # 3. Baixa o Estoque do Evento (ML por ML)[cite: 1]
            for ing_id, dose_ml in ingredientes:
                total_ml = float(dose_ml) * qtd
                cur.execute("""
                    UPDATE event_stocks 
                    SET quantity_used = quantity_used + %s 
                    WHERE event_id = %s AND ingredient_id = %s
                """, (total_ml, event_id, ing_id))

            # 4. Registra a Venda Financeira para o BI[cite: 1]
            cur.execute("""
                INSERT INTO sales (event_id, cocktail_id, bartender_name, client_name, price, cost)
                SELECT %s, %s, %s, %s, c.price, c.cost 
                FROM cocktails c WHERE c.id = %s
            """, (event_id, cocktail_id, payload['bartender'], client_name, cocktail_id))

        # 5. Atualiza o status do pedido para 'Entregue'
        cur.execute("UPDATE event_orders SET status = 'Entregue', updated_at = now() WHERE id = %s", (order_id,))
        
        conn.commit()
        return {"status": "sucesso", "message": "Estoque baixado e venda registrada."}

    except Exception as e:
        conn.rollback()
        print(f"Erro no KDS: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/orders/active")
def verificar_pedido_cliente(event_id: str, client_id: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Fazemos um JOIN com a tabela events para ele entender o Slug ("Festa-Teste")
        cur.execute("""
            SELECT eo.id, eo.status 
            FROM event_orders eo
            JOIN events e ON eo.event_id = e.id
            WHERE (e.custom_url_slug = %s OR e.id::text = %s)
              AND eo.client_id = %s 
              AND eo.status != 'Entregue'
            ORDER BY eo.created_at DESC LIMIT 1
        """, (event_id, event_id, client_id))
        
        pedido = cur.fetchone()
        
        if not pedido:
            return {"has_active_order": False}
            
        # Se tem pedido, busca os nomes dos drinks
        cur.execute("""
            SELECT c.name as nome, oi.quantity as qtd
            FROM event_order_items oi
            JOIN cocktails c ON oi.cocktail_id = c.id
            WHERE oi.order_id = %s
        """, (pedido['id'],))
        
        itens = cur.fetchall()
        
        return {
            "has_active_order": True,
            "order": {
                "status": pedido['status'],
                "itens": itens
            }
        }
    except Exception as e:
        print(f"Erro fatal em orders/active: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao checar pedido")
    finally:
        cur.close()
        conn.close()

# ==========================================
# ROTA: KDS - LISTAR PEDIDOS ATIVOS DA FESTA
# ==========================================
@app.get("/kds/orders/{event_id}")
def listar_pedidos_kds(event_id: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 1. TRADUTOR: Acha o ID real da festa (mesmo se o barman usar o link "Festa-Teste")
        cur.execute("""
            SELECT id FROM events 
            WHERE custom_url_slug = %s OR id::text = %s
        """, (event_id, event_id))
        evento = cur.fetchone()
        
        if not evento:
            return [] # Se não achar a festa, devolve lista vazia pro KDS não bugar

        id_verdadeiro = evento['id']

# 2. Busca os pedidos que estão na fila (Pendente, Preparando ou Pronto)
        cur.execute("""
            SELECT id, client_name, status, created_at 
            FROM event_orders
            WHERE event_id = %s AND status IN ('Pendente', 'Preparando', 'Pronto')
            ORDER BY created_at ASC
        """, (id_verdadeiro,))
        
        pedidos = cur.fetchall()

        # 3. Para cada pedido, busca os drinks que o cliente escolheu
        for p in pedidos:
            cur.execute("""
                SELECT c.name as nome, oi.quantity as qtd
                FROM event_order_items oi
                JOIN cocktails c ON oi.cocktail_id = c.id
                WHERE oi.order_id = %s
            """, (p['id'],))
            p['itens'] = cur.fetchall()

        return pedidos

    except Exception as e:
        print(f"Erro no KDS: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar pedidos para o KDS")
    finally:
        cur.close()
        conn.close()

# ==========================================
# ROTA: KDS - ATUALIZAR STATUS DO PEDIDO
# ==========================================
@app.patch("/orders/{order_id}/status")
def atualizar_status_pedido(order_id: str, payload: dict):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        novo_status = payload.get("status")
        
        # Opcional: Se quiser registrar o nome do bartender, pode pegar do payload aqui também
        
        cur.execute("""
            UPDATE event_orders 
            SET status = %s 
            WHERE id = %s
        """, (novo_status, order_id))
        conn.commit()
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pedido não encontrado no banco")
            
        return {"status": "sucesso", "novo_status": novo_status}
        
    except Exception as e:
        conn.rollback()
        print(f"Erro no KDS PATCH: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()



# ==========================================
# ROTA: LISTAR ORÇAMENTOS SALVOS DA CONTA (GET)
# ==========================================
@app.get("/orcamentos")
def listar_orcamentos(account_id: str): # Recebe o ID da conta ativo como parâmetro
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # AJUSTES: Adicionado filtro por account_id
        query = """
            SELECT 
                id, numero, cliente, data_evento, local, 
                qtd_pessoas, pacote_escolhido, valor_pessoa, 
                extras, total, drinks_selecionados, status, custo_estimado, valor_sugerido  -- <--- ADICIONE AQUI
            FROM budgets 
            WHERE account_id = %s
            ORDER BY numero DESC 
            LIMIT 50;
        """
        
        cur.execute(query, (account_id,))
        orcamentos_banco = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "dados": orcamentos_banco
        }
        
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA: SALVAR NOVO OU ATUALIZAR ORÇAMENTO
# ==========================================
@app.post("/orcamentos")
def salvar_orcamento(orc: NovoOrcamentoInput):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        drinks_jsonb = json.dumps(orc.drinks)

        # FLUXO 1: ATUALIZAR ORÇAMENTO EXISTENTE
        if orc.id:
            query_update = """
                UPDATE budgets SET
                    cliente = %s, data_evento = %s, local = %s, 
                    qtd_pessoas = %s, pacote_escolhido = %s, valor_pessoa = %s, 
                    extras = %s, total = %s, drinks_selecionados = %s, 
                    custo_estimado = %s, valor_sugerido = %s
                WHERE id = %s AND account_id = %s
                RETURNING numero;
            """
            cur.execute(query_update, (
                orc.cliente, orc.data_evento if orc.data_evento else None,
                orc.local, orc.qtd_pessoas, orc.pacote_escolhido, 
                orc.valor_pessoa, orc.extras, orc.total, 
                drinks_jsonb, orc.custo_estimado, orc.valor_sugerido,
                orc.id, orc.account_id
            ))
            
            resultado = cur.fetchone()
            if not resultado:
                raise HTTPException(status_code=404, detail="Orçamento não encontrado para atualização.")
                
            numero_final = resultado[0]
            mensagem_final = f"Orçamento {numero_final} atualizado com sucesso!"
            id_final = orc.id

        # FLUXO 2: CRIAR NOVO ORÇAMENTO
        else:
            cur.execute("SELECT COUNT(*) FROM budgets WHERE account_id = %s;", (orc.account_id,))
            total_existente = cur.fetchone()[0]
            numero_final = f"ORC-{str(total_existente + 1).zfill(4)}"
            
            query_insert = """
                INSERT INTO budgets (
                    account_id, numero, cliente, data_evento, local, 
                    qtd_pessoas, pacote_escolhido, valor_pessoa, extras, total, 
                    drinks_selecionados, status, custo_estimado, valor_sugerido
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            cur.execute(query_insert, (
                orc.account_id, numero_final, orc.cliente, 
                orc.data_evento if orc.data_evento else None,
                orc.local, orc.qtd_pessoas, orc.pacote_escolhido, 
                orc.valor_pessoa, orc.extras, orc.total, 
                drinks_jsonb, "Pendente", orc.custo_estimado, orc.valor_sugerido
            ))
            
            id_final = cur.fetchone()[0]
            mensagem_final = f"Novo orçamento {numero_final} criado com sucesso!"

        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso",
            "mensagem": mensagem_final,
            "budget_id": str(id_final),
            "numero_gerado": numero_final
        }
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA: ANALYTICS E RELATÓRIO DE VENDAS
# ==========================================
@app.get("/vendas")
def relatorio_vendas(event_id: str = 'ALL'):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # Fazemos um LEFT JOIN para buscar o nome do Drink baseado no cocktail_id
        query = """
            SELECT 
                s.id, s.event_id, s.price, s.frozen_cost, 
                s.created_at, s.user_name, c.name  -- 📍 CORRIGIDO DE 'c.nome' PARA 'c.name'
            FROM sales s
            LEFT JOIN cocktails c ON s.cocktail_id = c.id
        """
        params = []
        
        # Filtra por evento específico ou puxa o global
        if event_id != 'ALL':
            query += " WHERE s.event_id = %s::uuid"  # 📍 MANTIVE O ::uuid PARA PREVENIR ERROS DE TIPO
            params.append(event_id)
            
        query += " ORDER BY s.created_at DESC;"
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        vendas = []
        for r in rows:
            vendas.append({
                "id": str(r[0]),
                "event_id": str(r[1]) if r[1] else "",
                "preco": float(r[2]) if r[2] else 0.0,
                "custo": float(r[3]) if r[3] else 0.0,
                # Converte o Timestamp do Postgres para string ISO que o JS entende
                "hora": r[4].isoformat() if r[4] else None, 
                "usuario": r[5] if r[5] else "Sistema",
                "drink": r[6] if r[6] else "Drink Avulso/Excluído"
            })
            
        cur.close()
        conn.close()
        
        return {"status": "sucesso", "dados": vendas}
        
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# FECHAMENTO DE ESTOQUE (LOGÍSTICA REVERSA)
# ==========================================
@app.post("/events/{event_id}/retorno-estoque")
def processar_retorno_estoque(event_id: str, payload: PayloadRetorno):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        for item in payload.itens:
            # 1. Lê a situação atual daquele insumo no evento
            cur.execute("""
                SELECT quantity_sent, quantity_returned 
                FROM event_stocks 
                WHERE event_id = %s AND ingredient_id = %s
            """, (event_id, item.ingredient_id))
            
            row = cur.fetchone()
            if not row:
                continue # Se o insumo não foi enviado pro evento, pula
                
            qtd_sent = float(row[0] or 0)
            old_returned = float(row[1] or 0)
            new_returned = float(item.returned_quantity)
            
            # 2. A Mágica Matemática (Calcula apenas o Delta do que já estava no estoque central)
            delta_return = new_returned - old_returned 
            
            # 3. Atualiza o histórico do evento (APENAS o retorno, preserva o quantity_used!)
            cur.execute("""
                UPDATE event_stocks 
                SET quantity_returned = %s 
                WHERE event_id = %s AND ingredient_id = %s
            """, (new_returned, event_id, item.ingredient_id))
            
            # 4. Atualiza o estoque central físico
            cur.execute("""
                UPDATE ingredients 
                SET current_stock = current_stock + %s 
                WHERE id = %s
            """, (delta_return, item.ingredient_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Estoque conciliado com sucesso!"}
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print("Erro na conciliação de estoque:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
# LISTAR ESTOQUE ENVIADO PARA O EVENTO (GET)
# ==========================================
@app.get("/events/{event_id}/stocks")
def listar_estoque_evento(event_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # Fazemos um JOIN para trazer o nome do insumo e a unidade direto da tabela ingredients
        query = """
            SELECT 
                es.ingredient_id,
                i.name AS ingredient_name,
                i.brand,
                i.measurement_unit AS unit,
                es.quantity_sent,
                es.quantity_returned,
                es.quantity_used
            FROM event_stocks es
            JOIN ingredients i ON es.ingredient_id = i.id
            WHERE es.event_id = %s
        """
        
        cur.execute(query, (event_id,))
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Monta o JSON perfeitamente estruturado para o frontend ler
        estoque_evento = []
        for r in rows:
            estoque_evento.append({
                "ingredient_id": str(r[0]),
                "ingredient_name": r[1],
                "brand": r[2] or "",
                "unit": r[3],
                "quantity_sent": float(r[4] or 0),
                "quantity_returned": float(r[5] or 0),
                "quantity_used": float(r[6] or 0)
            })
            
        return estoque_evento
        
    except Exception as e:
        if conn:
            conn.close()
        print("Erro ao listar estoque do evento:", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# ROTA DE CLONAGEM DE RECEITA
# ==========================================
@app.post("/recipes/{cocktail_id}/clone")
def clonar_receita(cocktail_id: str, payload: CloneCocktail):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Busca a ficha técnica original
        cur.execute("""
            SELECT * FROM cocktails
            WHERE id = %s::uuid AND account_id = %s::uuid
        """, (cocktail_id, payload.account_id))
        
        original = cur.fetchone()
        if not original:
            raise HTTPException(status_code=404, detail="Ficha técnica original não encontrada.")

        # 2. Define o nome do clone para evitar bloqueio do banco de dados (UNIQUE)
        # Se o frontend não enviar um nome, colocamos " (Cópia)" automaticamente
        nome_clone = payload.novo_nome if payload.novo_nome else f"{original['name']} (Cópia)"

        # 3. Insere o Drink Clonado (Gera o novo ID)
        cur.execute("""
            INSERT INTO cocktails (
                account_id, name, category, drink_type, technique, 
                preparation_steps, description, sale_price, image_url, min_package_level
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id;
        """, (
            payload.account_id, nome_clone, original['category'], original['drink_type'],
            original['technique'], original['preparation_steps'], original['description'],
            original['sale_price'], original['image_url'], original['min_package_level']
        ))
        
        novo_cocktail_id = cur.fetchone()['id']

        # 4. Copia os Ingredientes (O "Pulo do Gato" da tabela relacional)
        # Esse comando SELECT insere todas as linhas de ingredientes do drink velho no drink novo de uma vez só!
        cur.execute("""
            INSERT INTO cocktail_ingredients (cocktail_id, ingredient_id, quantity)
            SELECT %s::uuid, ingredient_id, quantity
            FROM cocktail_ingredients
            WHERE cocktail_id = %s::uuid;
        """, (novo_cocktail_id, cocktail_id))

        # 5. Salva tudo!
        conn.commit()
        return {
            "status": "sucesso", 
            "mensagem": "Ficha clonada com sucesso!", 
            "novo_cocktail_id": novo_cocktail_id,
            "nome_clone": nome_clone
        }

    except Exception as e:
        if conn: conn.rollback()
        # Tratamento visual amigável se ele tentar clonar a cópia e o nome ficar duplicado
        if 'unique_drink_name_per_account' in str(e):
            raise HTTPException(status_code=400, detail=f"Você já possui uma receita chamada '{nome_clone}'. Renomeie a cópia anterior antes de clonar novamente.")
        print(f"ERRO CLONE: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

# ==========================================
# ROTA DE EXCLUSÃO DE DRINK
# ==========================================
@app.delete("/cocktails/{cocktail_id}")
def deletar_cocktail(cocktail_id: str, account_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # O banco de dados faz o trabalho pesado. O ON DELETE CASCADE
        # vai apagar os ingredientes atrelados a esse ID automaticamente.
        cur.execute("""
            DELETE FROM cocktails 
            WHERE id = %s::uuid AND account_id = %s::uuid
        """, (cocktail_id, account_id))
        
        conn.commit()
        return {"status": "sucesso", "mensagem": "Ficha técnica excluída."}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

class ImportPackPayload(BaseModel):
    account_id: str           # ID da agência do cliente que está comprando
    master_account_id: str    # ID da conta Aurora (Onde ficam os drinks perfeitos)
    sufixo: str = " (Premium)" # Adiciona isso no nome para não dar conflito de nome repetido

# ==========================================
# ROTA DE MARKETPLACE: IMPORTAR PACOTE
# ==========================================
@app.post("/marketplace/import-pack")
def importar_pacote_premium(payload: ImportPackPayload):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Busca todos os drinks da conta Mestre (Aurora)
        cur.execute("""
            SELECT * FROM cocktails WHERE account_id = %s::uuid
        """, (payload.master_account_id,))
        drinks_mestre = cur.fetchall()

        if not drinks_mestre:
            raise HTTPException(status_code=404, detail="Nenhum drink encontrado no pacote mestre.")

        # Dicionário de tradução de ingredientes: { id_ingrediente_mestre : id_ingrediente_cliente }
        mapa_ingredientes = {}

        # 2. Loop principal: Clonar os drinks um a um
        drinks_importados = 0
        for drink in drinks_mestre:
            nome_importado = f"{drink['name']}{payload.sufixo}"
            
            # Verifica se o cliente já tem um drink com esse exato nome para evitar o erro do UNIQUE
            cur.execute("SELECT id FROM cocktails WHERE account_id = %s::uuid AND name = %s", 
                       (payload.account_id, nome_importado))
            if cur.fetchone():
                continue # Se já tem, pula esse drink e vai pro próximo

            # Insere o drink para o cliente
            cur.execute("""
                INSERT INTO cocktails (
                    account_id, name, category, drink_type, technique, 
                    preparation_steps, description, sale_price, image_url, min_package_level
                ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (
                payload.account_id, nome_importado, drink['category'], drink['drink_type'],
                drink['technique'], drink['preparation_steps'], drink['description'],
                drink['sale_price'], drink['image_url'], drink['min_package_level']
            ))
            novo_drink_id = cur.fetchone()['id']
            drinks_importados += 1

            # 3. Puxa a receita (ingredientes) do drink mestre
            cur.execute("""
                SELECT * FROM cocktail_ingredients WHERE cocktail_id = %s::uuid
            """, (drink['id'],))
            receita_mestre = cur.fetchall()

            for item in receita_mestre:
                ingrediente_mestre_id = item['ingredient_id']
                
                # Se ainda não traduzimos esse ingrediente, temos que buscar ou criar no cliente
                if ingrediente_mestre_id not in mapa_ingredientes:
                    cur.execute("SELECT * FROM ingredients WHERE id = %s::uuid", (ingrediente_mestre_id,))
                    ing_original = cur.fetchone()

                    # Procura se o cliente já tem um ingrediente com o mesmo NOME e TIPO
                    cur.execute("""
                        SELECT id FROM ingredients 
                        WHERE account_id = %s::uuid AND name = %s AND type_id = %s::uuid
                    """, (payload.account_id, ing_original['name'], ing_original['type_id']))
                    ing_cliente = cur.fetchone()

                    if ing_cliente:
                        # O cliente já tem! Usa o ID dele
                        mapa_ingredientes[ingrediente_mestre_id] = ing_cliente['id']
                    else:
                        # O cliente não tem. Cria um ingrediente novo no estoque dele!
                        cur.execute("""
                            INSERT INTO ingredients (
                                account_id, type_id, name, brand, measurement_unit, package_quantity, current_cost_price
                            ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s) RETURNING id;
                        """, (
                            payload.account_id, ing_original['type_id'], ing_original['name'], 
                            ing_original['brand'], ing_original['measurement_unit'], 
                            ing_original['package_quantity'], ing_original['current_cost_price'] # <- Preço adicionado aqui!
                        ))
                        mapa_ingredientes[ingrediente_mestre_id] = cur.fetchone()['id']

                # 4. Finalmente, liga o ingrediente traduzido ao novo drink!
                cur.execute("""
                    INSERT INTO cocktail_ingredients (cocktail_id, ingredient_id, quantity)
                    VALUES (%s::uuid, %s::uuid, %s)
                """, (novo_drink_id, mapa_ingredientes[ingrediente_mestre_id], item['quantity']))

        conn.commit()
        return {
            "status": "sucesso", 
            "mensagem": f"{drinks_importados} fichas técnicas Premium importadas com sucesso!",
            "ingredientes_processados": len(mapa_ingredientes)
        }

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

# ==========================================
# MODELOS DE DADOS (PYDANTIC)
# ==========================================
class EventoPayload(BaseModel):
    account_id: str
    nome_contratante: str
    data_evento: str
    local_evento: str
    convidados: int
    duracao_horas: int
    duracao_minutos: int
    valor_contrato: float
    orcamento_origem_id: str
    status: str

class StatusOrcamentoPayload(BaseModel):
    status: str

# ==========================================
# ROTA 1: CRIAR EVENTO (Vindo do Orçamento)
# ==========================================
@app.post("/events")
def criar_evento_via_orcamento(payload: EventoPayload):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # ⚠️ ATENÇÃO: Verifique se os nomes das colunas abaixo batem exatamente 
        # com os nomes que você criou na sua tabela 'events' no Supabase!
        cur.execute("""
            INSERT INTO events (
                account_id, contratante, data_evento, local, 
                convidados, duracao_horas, duracao_minutos, valor_contrato, 
                orcamento_origem_id, status
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s)
            RETURNING id;
        """, (
            payload.account_id, payload.nome_contratante, payload.data_evento, 
            payload.local_evento, payload.convidados, payload.duracao_horas, 
            payload.duracao_minutos, payload.valor_contrato, 
            payload.orcamento_origem_id, payload.status
        ))
        
        novo_id = cur.fetchone()['id']
        conn.commit()
        return {"status": "sucesso", "evento_id": novo_id}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

# ==========================================
# ROTA 2: ATUALIZAR STATUS DO ORÇAMENTO
# ==========================================
@app.patch("/orcamentos/{orcamento_id}/status")
def atualizar_status_orcamento(orcamento_id: str, payload: StatusOrcamentoPayload):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # ⚠️ Ajuste o nome da tabela 'budgets' ou 'orcamentos' conforme o seu banco
        cur.execute("""
            UPDATE budgets 
            SET status = %s 
            WHERE id = %s::uuid
        """, (payload.status, orcamento_id))
        
        conn.commit()
        return {"status": "sucesso"}

    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()