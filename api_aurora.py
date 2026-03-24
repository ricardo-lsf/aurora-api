from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
from typing import Optional, List

app = FastAPI(title="Aurora Bartenders API")

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
    category_id: str
    name: str
    brand: str
    measurement_unit: str  # Ex: ml, g, un
    package_quantity: float # Ex: 1000 (para 1 litro)

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
    description: Optional[str] = ""
    category: str
    sale_price: float
    image_url: Optional[str] = ""
    # Aqui é o pulo do gato: uma lista com a receita embutida!
    recipe: List[IngredienteReceita]


# Função para conectar no banco local
def get_db_connection():
    try:
        # Apontando o motor para a nuvem do Supabase!
        conn = psycopg2.connect("postgresql://postgres.xnvznbmwxvflavmnmxxx:AennUoVaXZ16EG5g@aws-1-sa-east-1.pooler.supabase.com:5432/postgres")
        return conn
    except Exception as e:
        print(f"Erro ao conectar no banco: {e}")
        return None

# ==========================================
# NOSSA PRIMEIRA ROTA (ENDPOINT)
# ==========================================
@app.get("/drinks/{account_id}")
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
                e.event_name AS nome_da_festa,
                e.event_date AS data_da_festa,
                c.name AS nome_do_drink,
                c.description AS descricao,
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
# NOSSA QUARTA ROTA: SALVAR O CARDÁPIO DA FESTA
# ==========================================
@app.post("/events/{event_id}/menu")
def salvar_cardapio(event_id: str, menu: NovoMenu):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # 1. Limpeza de Segurança (Se já tinha cardápio antes, apagamos para não duplicar)
        cur.execute("DELETE FROM event_menus WHERE event_id = %s;", (event_id,))
        
        # 2. O comando base de inserção
        query = """
            INSERT INTO event_menus (event_id, cocktail_id, display_order)
            VALUES (%s, %s, %s);
        """
        
        # 3. O Loop Inteligente: Lemos a lista e salvamos um por um já com a posição (index)
        for posicao, drink_id in enumerate(menu.drinks, start=1):
            cur.execute(query, (event_id, drink_id, posicao))
            
        # 4. Confirma a transação inteira no banco
        conn.commit()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "mensagem": f"Cardápio salvo com {len(menu.drinks)} drinks na ordem correta!"
        }
        
    except Exception as e:
        conn.rollback() # Cancela tudo se der erro no meio do caminho
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
        

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
                id,
                name AS insumo,
                current_stock AS estoque_ml_g,
                measurement_unit AS unidade,
                current_cost_price AS custo_ultima_embalagem,
                ROUND((current_stock / NULLIF(package_quantity, 0)), 2) AS qtd_embalagens_estoque,
                ROUND((current_cost_price / NULLIF(package_quantity, 0)), 4) AS custo_por_gota,
                ROUND((current_stock / NULLIF(package_quantity, 0)) * current_cost_price, 2) AS dinheiro_parado
            FROM ingredients
            WHERE account_id = %s
            ORDER BY name;
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
# NOSSA OITAVA ROTA: CRIAR DRINK COM FICHA TÉCNICA
# ==========================================
@app.post("/cocktails/")
def criar_drink_completo(drink: NovoCocktail):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor()
        
        # 1. Geramos o ID único para o novo drink
        novo_drink_id = str(uuid.uuid4())
        
        # 2. Inserimos o "Cabeçalho" do drink na tabela principal
        query_drink = """
            INSERT INTO cocktails (id, account_id, name, description, category, sale_price, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(query_drink, (
            novo_drink_id, drink.account_id, drink.name, 
            drink.description, drink.category, drink.sale_price, drink.image_url
        ))
        
        # 3. O Loop da Ficha Técnica: ligando cada dose ao drink novo
        query_receita = """
            INSERT INTO cocktail_ingredients (cocktail_id, ingredient_id, quantity)
            VALUES (%s, %s, %s);
        """
        for item in drink.recipe:
            cur.execute(query_receita, (novo_drink_id, item.ingredient_id, item.quantity))
            
        # 4. O Gran Finale: Confirma TUDO de uma vez!
        conn.commit()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "mensagem": f"Drink '{drink.name}' criado com {len(drink.recipe)} ingredientes na ficha técnica!",
            "drink_id": novo_drink_id
        }
        
    except Exception as e:
        # Se der BO em qualquer etapa, desfaz TUDO. Zero lixo no banco!
        conn.rollback() 
        conn.close()
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
                image_url 
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
@app.get("/events/{event_id}/menu")
def listar_menu_evento(event_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Erro de conexão com o banco")
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # O JOIN mágico: Pega só os drinks que estão na tabela event_menus para esta festa
        # E já traz ordenado pelo 'display_order' que salvamos antes!
        query = """
            SELECT 
                c.id, 
                c.name AS drink_nome, 
                c.sale_price AS preco_venda, 
                c.image_url
            FROM event_menus em
            JOIN cocktails c ON em.cocktail_id = c.id
            WHERE em.event_id = %s
            ORDER BY em.display_order;
        """
        
        cur.execute(query, (event_id,))
        drinks_evento = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "quantidade": len(drinks_evento), 
            "dados": drinks_evento
        }
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
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
        
        # O JOIN relacional: Pega os ingredientes e quantidades exatas deste drink
        query = """
            SELECT 
                i.name AS ingrediente, 
                ci.quantity AS quantidade, 
                ci.unit AS unidade
            FROM cocktail_ingredients ci
            JOIN ingredients i ON ci.ingredient_id = i.id
            WHERE ci.cocktail_id = %s
            ORDER BY i.name;
        """
        
        cur.execute(query, (cocktail_id,))
        receita = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "status": "sucesso", 
            "dados": receita
        }
        
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=400, detail=str(e))