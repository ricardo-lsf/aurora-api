```mermaid
graph TD
    %% Entidades Externas
    Forn[🛒 Fornecedor / Atacadista]
    PDV[📱 Tablet do Bartender]
    
    %% Tabelas do Banco de Dados
    Cat[(Catálogo & Estoque Geral<br/>'ingredients')]
    Ficha[(Ficha Técnica<br/>'cocktail_ingredients')]
    EstqEv[(Estoque do Evento<br/>'event_stocks')]
    Caixa[(Financeiro & Vendas<br/>'sales')]

    %% Fluxo de Dados
    Forn -- "1. Entrada (abrirModalEntrada)\nSoma Volume e Atualiza Custo" --> Cat
    Cat -- "2. Logística (Carregar Caminhão)\nSubtrai do Geral, Envia pro Evento" --> EstqEv
    Ficha -. "Consulta de Receita" .-> PDV
    PDV -- "3. Venda (Drink Solicitado)" --> EstqEv
    EstqEv -- "Baixa Exclusiva\n(Soma em quantity_used)" --> Caixa
    EstqEv -- "4. Retorno de Carga\n(Devolve Sobra Física)" --> Cat
    Cat -. "Cálculo do Frozen Cost" .-> Caixa

    classDef db fill:#f9f9f9,stroke:#333,stroke-width:2px;
    class Cat,Ficha,EstqEv,Caixa db;
