from fastapi import FastAPI, APIRouter, HTTPException
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


app = FastAPI(title="Aurora Bartenders API")

# Configuração de CORS - Garanta que está assim:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # O "*" permite que qualquer site (inclusive seu localhost) acesse a API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Libera a pasta de imagens para acesso público
app.mount("/imagens", StaticFiles(directory="imagens"), name="imagens")

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


# ... (suas configurações de app e rotas antigas) ...

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
def listar_eventos_ativos():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")

    try:
        cur = conn.cursor()
        
        # O CADEADO DUPLO: Exatamente como você pediu!
        # Só vai pro celular do bartender se o Gerente ativou (TRUE) E o bar abriu ('aberto')
        cur.execute("SELECT id, name FROM events WHERE is_active = TRUE AND status = 'aberto'")
        
        eventos = cur.fetchall()
        cur.close()
        conn.close()

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

class EventCreate(BaseModel):
    nome: str
    account_id: Optional[str] = "a57c20f3-526a-41f4-8b95-d4cd7cd2e362" # <--- O Pulo do Gato!
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
                upfront_perc = %s
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
# CONFIGURAÇÃO DE SEGURANÇA (CORS)
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite que qualquer front-end (até o seu localhost) acesse a API
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os comandos (GET, POST, etc.)
    allow_headers=["*"],  # Permite qualquer formato de cabeçalho
)

# O "Molde" (Schema) para criar um evento
class NovoEvento(BaseModel):
    account_id: str
    event_name: str
    event_date: str          # Formato esperado: 'YYYY-MM-DD'
    custom_url_slug: str     # Ex: 'niver-do-heitor'
    status: Optional[str] = 'confirmed' # Se o app não mandar, assume 'confirmed'

# ==========================================
# NOVOS MOLDES: INSUMOS E COMPRAS
# ==========================================
class NovoInsumo(BaseModel):
    account_id: str
    type_id: str  # Mudamos de category_id para type_id
    name: str
    brand: str
    measurement_unit: str
    package_quantity: float

class NovaCompra(BaseModel):
    ingredient_id: str
    packages_bought: float
    total_paid: float
    supplier_name: Optional[str] = "Não informado"

# ==========================================
# NOVOS MOLDES: A FICHA TÉCNICA DO DRINK
# ==========================================
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
    recipe: List[IngredienteReceita]

class EdicaoInsumo(BaseModel):
    name: str
    brand: Optional[str] = ""
    type_name: str
    measurement_unit: str
    package_quantity: float
    current_cost_price: float


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
        
        
# ==========================================
# NOSSA TERCEIRA ROTA: CRIAR UM NOVO EVENTO
# ==========================================
@app.post("/events/")
def criar_evento(evento: NovoEvento):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # O Python gera um UUID novinho para essa festa
        novo_event_id = str(uuid.uuid4())
        
        # O comando de inserção (usando %s para segurança contra hackers)
        query = """
            INSERT INTO events (id, account_id, event_name, event_date, custom_url_slug, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        
        # A tupla com os valores exatos que vieram do aplicativo
        valores = (
            novo_event_id, 
            evento.account_id, 
            evento.event_name, 
            evento.event_date, 
            evento.custom_url_slug, 
            evento.status
        )
        
        cur.execute(query, valores)
        
        # O COMANDO MÁGICO: No INSERT, precisamos dar "Commit" para salvar de verdade!
        conn.commit()
        
        cur.close()
        conn.close()
        
        # Devolvemos uma resposta de sucesso para o aplicativo
        return {
            "status": "sucesso", 
            "mensagem": "Festa criada com sucesso!", 
            "event_id": novo_event_id,
            "link_do_cardapio": f"aurorabartenders.com/{evento.custom_url_slug}"
        }
        
    except Exception as e:
        # Se der qualquer erro (ex: slug duplicado), desfazemos a operação
        conn.rollback() 
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        
        
# ==========================================
# O "MOLDE" DA LISTA DE DRINKS
# ==========================================
class NovoMenu(BaseModel):
    # Uma lista contendo os UUIDs dos drinks, na ordem em que devem aparecer na tela
    drinks: List[str] 

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
# O "MOLDE" PARA MULTIPLOS INSUMOS
# ==========================================
class ItemCarga(BaseModel):
    ingredient_id: str
    quantity: float

class CargaEvento(BaseModel):
    event_id: str
    itens: List[ItemCarga]

# ==========================================
# CARREGAR ESTOQUE (VALIDADA)
# ==========================================
@app.post("/inventory/load-event")
def carregar_estoque_evento(payload: CargaEvento):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for item in payload.itens:
            # 1. Tira do estoque central
            cur.execute("UPDATE ingredients SET current_stock = current_stock - %s WHERE id = %s", 
                        (item.quantity, item.ingredient_id))
            
            # 2. Aloca no estoque do evento
            query_upsert = """
                INSERT INTO event_stocks (event_id, ingredient_id, quantity_sent)
                VALUES (%s, %s, %s)
                ON CONFLICT (event_id, ingredient_id) 
                DO UPDATE SET quantity_sent = event_stocks.quantity_sent + EXCLUDED.quantity_sent;
            """
            cur.execute(query_upsert, (payload.event_id, item.ingredient_id, item.quantity))
        
        conn.commit()
        return {"status": "sucesso", "detalhes": f"{len(payload.itens)} insumos carregados."}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
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

        # 2. Inserimos os novos, mas usamos ON CONFLICT para não zerar o que já existe
        # Nota: Para isso funcionar, sua tabela event_menus precisa de uma constraint UNIQUE(event_id, cocktail_id)
        query_upsert = """
            INSERT INTO event_menus (event_id, cocktail_id, display_order)
            VALUES (%s, %s, %s)
            ON CONFLICT (event_id, cocktail_id) DO NOTHING;
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
@app.get("/events/{event_id}/menu")
def buscar_cardapio_evento_admin(event_id: str):
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

from pydantic import BaseModel
from typing import Optional

# 1. O Molde do que o seu PDV (index.html) vai enviar para a API
class NovaVenda(BaseModel):
    event_id: str
    cocktail_id: str
    price: float  # Se for Open Bar, o PDV vai mandar 0.00. Se for Cash Bar, manda o valor pago.
    user_name: Optional[str] = "Bartender"

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
class EstornoVenda(BaseModel):
    sale_id: str
    event_id: str

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
        
        # Inserimos o Cabeçalho (AGORA COM TECHNIQUE E DRINK_TYPE)
        query_drink = """
            INSERT INTO cocktails (id, account_id, name, preparation_steps, category, technique, drink_type, sale_price, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(query_drink, (
            novo_drink_id, drink.account_id, drink.name, 
            drink.preparation_steps, drink.category, drink.technique, drink.drink_type, drink.sale_price, drink.image_url
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
        
        # 1. Atualiza o Cabeçalho do drink
        query_drink = """
            UPDATE cocktails 
            SET name = %s, preparation_steps = %s, category = %s, technique = %s, drink_type = %s, sale_price = %s, image_url = %s
            WHERE id = %s AND account_id = %s;
        """
        cur.execute(query_drink, (
            drink.name, drink.preparation_steps, drink.category, drink.technique, drink.drink_type, 
            drink.sale_price, drink.image_url, cocktail_id, drink.account_id
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
                preparation_steps
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
# NOSSA DÉCIMA ROTA: LISTAR O CARDÁPIO EXATO DO EVENTO
# ==========================================
@app.get("/events/{event_id}/menu") # Mantenha a rota que já existe no seu código
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

        # 2. Busca os drinks e faz o JOIN DUPLO nos insumos!
        cur.execute("""
            SELECT 
                c.id, 
                c.name AS drink_nome, 
                c.sale_price AS preco_venda, 
                c.image_url,
                (
                    -- Magia do Postgres: Atravessa a ponte e junta os nomes separados por vírgula!
                    SELECT STRING_AGG(i.name, ', ') 
                    FROM cocktail_ingredients ci 
                    JOIN ingredients i ON ci.ingredient_id = i.id
                    WHERE ci.cocktail_id = c.id
                ) AS descricao,
                em.planned_quantity
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
# NOSSA DÉCIMA PRIMEIRA ROTA: BUSCAR RECEITA DO DRINK (FICHA TÉCNICA)
# ==========================================
@app.get("/cocktails/{cocktail_id}/recipe")
def ver_receita(cocktail_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Busca os textos de preparo do próprio drink (1 linha)
        # VERIFIQUE: Se os nomes das colunas forem diferentes no seu banco, altere aqui!
        cur.execute("SELECT technique, preparation_steps FROM cocktails WHERE id = %s;", (cocktail_id,))
        drink_info = cur.fetchone()
        
        # 2. Busca a lista de ingredientes (várias linhas) com a coluna corrigida
        query_ingredientes = """
            SELECT 
                i.id AS ingrediente_id,    -- CORREÇÃO: O ID ESTAVA FALTANDO!
                i.name AS ingrediente, 
                ci.quantity AS quantidade, 
                i.measurement_unit AS unidade
            FROM cocktail_ingredients ci
            JOIN ingredients i ON ci.ingredient_id = i.id
            WHERE ci.cocktail_id = %s
            ORDER BY i.name;
        """
        cur.execute(query_ingredientes, (cocktail_id,))
        ingredientes = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Empacota o combo completo e manda para o Front-end!
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
def registrar_venda(event_id: str, cocktail_id: str, user_name: str = "Desconhecido"):
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
# NOSSA DÉCIMA QUARTA ROTA: BUSCAR EVENTOS ATIVOS (PREPARADO PARA MÚLTIPLOS EVENTOS)
# ==========================================

    
# ==========================================
# NOSSA DÉCIMA QUINTA ROTA: LOGIN DA EQUIPE (STAFF)
# ==========================================
@app.get("/login/{phone}")
def login_staff(phone: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Busca o funcionário pelo telefone e verifica se está ativo
        cur.execute("SELECT id, name, role FROM staff WHERE phone = %s AND status = 'ativo';", (phone,))
        user = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if user:
            # Se achou, devolve sucesso e os dados da pessoa
            return {"status": "sucesso", "usuario": user}
        else:
            # Se não achou, devolve erro 404
            raise HTTPException(status_code=404, detail="Telefone não cadastrado ou inativo")
            
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
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
def list_events():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Traz todos os eventos ordenados pela data (os mais recentes primeiro)
        cur.execute("SELECT * FROM events ORDER BY event_date DESC;")
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
class EventStatus(BaseModel):
    status: str

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
    
# Molde para receber a atualização de estoque
class EstoqueDrink(BaseModel):
    quantidade: int

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
# ROTA: LISTAR EQUIPE (STAFF)
# ==========================================
@app.get("/team")
def listar_equipe():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # ATENÇÃO AQUI: Verifique se a coluna do nome na tabela STAFF se chama 'name', 'nome', etc.
        # Vou assumir 'name' como padrão do Supabase, mas ajuste se for 'nome'.
        cur.execute("SELECT name FROM STAFF ORDER BY name ASC")
        return cur.fetchall()
    except Exception as e:
        print(f"Erro ao buscar equipe (STAFF): {e}")
        return []
    finally:
        cur.close()
        conn.close()