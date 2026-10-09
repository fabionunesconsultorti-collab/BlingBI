import random
from datetime import datetime, timedelta, date
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.financial import FinancialEntry
from app.models.setting import Setting
from app.models.fashion import ConditionalBag, ProductReturn, SellerAttendance, CustomerSurvey

# =============================================================================
# METADADOS DOS NICHOS DE DEMONSTRAÇÃO
# =============================================================================
NICHE_METADATA = {
    "fashion": {
        "id": "fashion",
        "name": "Moda & Vestuário",
        "icon": "👗",
        "badge": "Vestuário & Malas",
        "description": "Vestidos, jeanswear, alfaiataria, bolsas, tamanhos, cores, malas condicionais e consultoria de estilo.",
        "avg_ticket": "R$ 380,00",
        "channels": ["WhatsApp VIP", "Loja Física", "Instagram Direct", "E-commerce"],
        "default_sellers": ["Natalia Ferruci", "Camila Duarte"]
    },
    "furniture_appliances": {
        "id": "furniture_appliances",
        "name": "Movelaria & Eletrodomésticos",
        "icon": "🛋️",
        "badge": "Ticket Médio Alto",
        "description": "Sofás retráteis, salas de jantar, guarda-roupas, geladeiras frost free, TVs 4K e lavadoras de alto valor.",
        "avg_ticket": "R$ 2.450,00",
        "channels": ["Showroom / Loja Física", "Site Oficial", "Televendas & WhatsApp", "Marketplace Magalu"],
        "default_sellers": ["Roberto Movelaria", "Ana Paula Decor"]
    },
    "food_restaurant": {
        "id": "food_restaurant",
        "name": "Lanchonete, Bar & Restaurante",
        "icon": "🍔",
        "badge": "Alta Frequência / Delivery",
        "description": "Burgers artesanais, porções, pizzas fermentação natural, chopps artesanais, salão e delivery iFood.",
        "avg_ticket": "R$ 68,00",
        "channels": ["Salão / Mesa", "Delivery iFood", "Balcão / Retirada", "WhatsApp Delivery"],
        "default_sellers": ["Garçom Salão", "Atendente Balcão"]
    },
    "home_varieties": {
        "id": "home_varieties",
        "name": "Utilidades Domésticas & Variedades",
        "icon": "🏠",
        "badge": "Cesta com Múltiplos Itens",
        "description": "Potes herméticos, panelas antiaderentes, mops giratórios, organizadores acrílicos e mesa posta.",
        "avg_ticket": "R$ 145,00",
        "channels": ["Loja Física", "Shopee", "Mercado Livre", "Site Oficial"],
        "default_sellers": ["Vendedor Loja", "Atendimento E-commerce"]
    },
    "toys": {
        "id": "toys",
        "name": "Loja de Brinquedos & Lazer",
        "icon": "🧸",
        "badge": "Presentes & Lúdico",
        "description": "Jogos de tabuleiro, blocos de montar, bonecas reborn, carrinhos controle remoto, pistas e pelúcias.",
        "avg_ticket": "R$ 160,00",
        "channels": ["Loja de Shopping", "Mercado Livre", "Shopee", "WhatsApp Presentes"],
        "default_sellers": ["Consultor Infantil", "Atendimento Web"]
    },
    "tech_mobile": {
        "id": "tech_mobile",
        "name": "Artigos para Celular & Informática",
        "icon": "📱",
        "badge": "Giro Rápido & Periféricos",
        "description": "Películas 3D, cases antichoque, carregadores GaN turbo, fones TWS, mouses gamers e teclados mecânicos.",
        "avg_ticket": "R$ 125,00",
        "channels": ["Balcão / Loja Física", "Mercado Livre", "Shopee", "WhatsApp Express"],
        "default_sellers": ["Especialista Tech", "Balcão Acessórios"]
    }
}

# =============================================================================
# CATÁLOGOS DE PRODUTOS POR NICHO
# =============================================================================
NICHE_PRODUCTS = {
    "fashion": [
        ("VEST-MIDI-FLORAL", "Vestido Midi Floral Evasê", 389.90, 160.00, 35, "Vestidos", "M", "Floral / Terracota", "Casual Chic"),
        ("BLAZER-LINHO-OFF", "Blazer Linho Puro Estruturado", 549.90, 240.00, 22, "Alfaiataria", "G", "Off White", "Alfaiataria"),
        ("CALCA-ALF-PRETA", "Calça Alfaiataria Cenoura com Cinto", 319.90, 130.00, 45, "Alfaiataria", "38", "Preto Clássico", "Alfaiataria"),
        ("JEANS-WIDE-LEG", "Calça Jeans Wide Leg Cintura Alta", 299.90, 120.00, 60, "Jeanswear", "40", "Azul Médio", "Urbano / Casual"),
        ("CAMISA-SEDA-AZUL", "Camisa Manga Longa Toque de Seda", 279.90, 110.00, 30, "Blusas & Camisas", "P", "Azul Serenity", "Elegante"),
        ("CROPPED-TRICOT", "Cropped Tricot Canelado Decote V", 159.90, 60.00, 50, "Blusas & Camisas", "M", "Fúcsia Vibrante", "Casual"),
        ("CONJ-RESORT-VERAO", "Conjunto Resort Coleção Verão (Top + Shorts)", 429.90, 180.00, 25, "Conjuntos", "M", "Verde Oliva", "Resort"),
        ("VEST-FESTA-PAETE", "Vestido Longo Gala Paetê", 899.90, 390.00, 15, "Festas & Noite", "P", "Dourado Champagne", "Gala"),
        ("JAQUETA-COURO-ECO", "Jaqueta Biker Couro Ecológico", 499.90, 210.00, 28, "Casacos & Jaquetas", "G", "Preto", "Moderno"),
        ("SAIA-PLISSADA-MIDI", "Saia Plissada Midi Acetinada", 259.90, 95.00, 40, "Saias", "M", "Rosé Gold", "Romântico Chic"),
        ("BOLSA-COURO-TOTE", "Bolsa Tote em Couro Legítimo Alça Dupla", 649.90, 280.00, 18, "Acessórios & Bolsas", "Único", "Caramelo", "Elegante"),
        ("SCARPIN-SALTO-BLOCO", "Scarpin Couro Pelica Salto Bloco 7cm", 369.90, 150.00, 24, "Calçados", "37", "Nude", "Clássico")
    ],
    "furniture_appliances": [
        ("SOFA-RETR-GRAFITE", "Sofá Retrátil e Reclinável 3 Lugares Veludo Grafite", 2499.90, 1250.00, 15, "Sala de Estar", None, "Grafite", "Moderno"),
        ("MESA-JANT-6CAD", "Mesa de Jantar 6 Cadeiras Madeira Maciça Tampo Vidro", 1999.90, 980.00, 12, "Sala de Jantar", None, "Off White / Freijó", "Contemporâneo"),
        ("GR-ROUPA-CASAL-6P", "Guarda-Roupa Casal 6 Portas e 4 Gavetas com Espelho", 1789.90, 890.00, 18, "Quarto", None, "Freijó / Branco", "Clássico"),
        ("CAMA-BOX-QUEEN", "Cama Box Queen Molas Ensacadas Euro Pillow Sono Perfeito", 1490.00, 740.00, 25, "Quarto", "Queen", "Cinza Chumbo", "Conforto"),
        ("GELAD-FROST-450L", "Geladeira Frost Free Inverse Inox 450L Duplex Classe A", 4299.00, 2850.00, 10, "Linha Branca", None, "Inox Escovado", "Tecnologia"),
        ("FOGAO-5BOCAS-VIDRO", "Fogão 5 Bocas Mesa de Vidro Temperado Bivolt", 1649.00, 990.00, 14, "Linha Branca", None, "Preto / Inox", "Gourmet"),
        ("SMART-TV-55-4K", "Smart TV 55' 4K QLED HDR Wi-Fi Dolby Vision", 2799.00, 1890.00, 20, "Áudio & Vídeo", "55 polegadas", "Preto", "High-Tech"),
        ("LAVA-SECA-11KG", "Máquina de Lavar e Secar Roupas 11kg Motor Inverter Inox", 3890.00, 2600.00, 8, "Linha Branca", None, "Inox Titanium", "Eficiência"),
        ("MICRO-32L-GRILL", "Micro-ondas 32L Espelhado Função Grill Inox", 789.90, 480.00, 30, "Eletroportáteis", None, "Espelhado", "Praticidade"),
        ("PAINEL-TV-65-LED", "Painel Home Theater Suspenso até 65' com Fita LED", 649.90, 310.00, 22, "Sala de Estar", None, "Ripado Freijó", "Design"),
        ("POLTRONA-GIRAT-BEGE", "Poltrona Giratória Base Madeira Linho Bege Confort", 589.90, 290.00, 16, "Decoração & Sala", None, "Linho Bege", "Elegante"),
        ("AIRFRYER-5L-DIGITAL", "Fritadeira Elétrica Air Fryer 5.5L Painel Digital", 459.90, 260.00, 40, "Eletroportáteis", None, "Preto Fosco", "Gourmet"),
        ("CAFETEIRA-EXPRESSO", "Cafeteira Expresso Automática Grãos Inox 15 Bar", 1290.00, 750.00, 12, "Eletroportáteis", None, "Aço Inox", "Premium")
    ],
    "food_restaurant": [
        ("BURGER-ANGUS-BACON", "Burger Artesanal Angus Bacon 160g com Queijo Cheddar", 38.90, 14.50, 150, "Burgers Artesanais", None, None, "Gourmet"),
        ("DOUBLE-MONSTER-CHEESE", "Double Monster Cheddar Bacon (2x Carnes 140g + Molho)", 46.90, 18.00, 120, "Burgers Artesanais", None, None, "Especial"),
        ("BATATA-RUSTICA-COSTELA", "Batata Rústica com Costela Desfiada e Sour Cream 600g", 49.90, 16.80, 80, "Porções & Petiscos", None, None, "Compartilhar"),
        ("PIZZA-MARGHERITA-NAT", "Pizza Fermentação Natural Margherita Di Bufala 35cm", 68.90, 22.00, 90, "Pizzas Especiais", "35cm", None, "Tradicional"),
        ("PIZZA-COSTELA-BBQ", "Pizza Costela ao Barbecue com Catupiry Original 35cm", 74.90, 26.00, 70, "Pizzas Especiais", "35cm", None, "Chef"),
        ("CHOPP-IPA-500ML", "Chopp Artesanal IPA 500ml Puro Malte Tropical", 18.90, 6.20, 300, "Chopps & Cervejas", "500ml", "Dourado Intenso", "Artesanal"),
        ("CHOPP-PILSEN-500ML", "Chopp Pilsen Premium Gelado Caneca 500ml", 13.90, 4.10, 450, "Chopps & Cervejas", "500ml", "Dourado Cristalino", "Clássico"),
        ("COMBO-FAMILIA-BURGER", "Combo Família: 2 Burgers Angus + Porção Batata + 2 Refris", 98.90, 36.00, 60, "Combos Promocionais", None, None, "Família"),
        ("REFRIGERANTE-LATA", "Refrigerante Lata 350ml (Coca-Cola, Guaraná, Zero)", 7.50, 2.80, 500, "Bebidas", "350ml", None, "Bebidas"),
        ("SUCO-NATURAL-450ML", "Suco de Laranja Natural Integral da Fruta 450ml", 11.90, 3.50, 200, "Bebidas", "450ml", "Laranja", "Natural"),
        ("PETIT-GATEAU-SORVETE", "Petit Gâteau com Sorvete Artesanal de Baunilha e Calda", 26.90, 8.50, 75, "Sobremesas", None, "Chocolate", "Doces"),
        ("ISCAS-TILAPIA-TARTARO", "Iscas de Tilápia Crocante com Molho Tártaro da Casa 500g", 54.90, 19.50, 65, "Porções & Petiscos", None, None, "Petisco"),
        ("DADINHOS-TAPIOCA", "Dadinhos de Tapioca com Geléia de Pimenta Defumada", 34.90, 10.20, 85, "Porções & Petiscos", None, None, "Entrada")
    ],
    "home_varieties": [
        ("POTES-HERM-5PC", "Jogo de 5 Potes Herméticos Vidro Borossilicato Tampa Bambu", 139.90, 56.00, 45, "Cozinha & Organização", None, "Transparente / Bambu", "Sustentável"),
        ("ORG-GAVETA-ACRILICO", "Kit 6 Organizadores de Gavetas Acrílico Cristal Modular", 69.90, 24.00, 70, "Organização do Lar", None, "Transparente", "Minimalista"),
        ("JG-PANELAS-CERAMICA", "Jogo de Panelas Cerâmica Antiaderente 5 Peças Indução", 349.90, 160.00, 30, "Cozinha & Panelas", None, "Terracota Cobre", "Premium"),
        ("MOP-GIRATORIO-360", "Mop Giratório 360° com Balde Duplo Lava e Centrifuga", 119.90, 48.00, 60, "Limpeza Prática", None, "Turquesa", "Facilidade"),
        ("GARRAFA-TERM-1L", "Garrafa Térmica Inox Escovado 1L Café e Chá 24h", 89.90, 32.00, 80, "Mesa Posta", "1 Litro", "Inox Escovado", "Moderno"),
        ("ESCORREDOR-INOX-2AND", "Escorredor de Pratos Inox 2 Andares com Porta Copos", 129.90, 51.00, 35, "Cozinha & Organização", None, "Inox Brilhante", "Durabilidade"),
        ("KIT-SILICONE-12PC", "Kit 12 Utensílios de Cozinha em Silicone Cabo Madeira", 99.90, 38.00, 90, "Cozinha & Utensílios", None, "Verde Menta", "Prático"),
        ("SUP-ARAMADO-PRATEL", "Suporte Aramado Organizador para Prateleira de Armário", 49.90, 16.00, 110, "Organização do Lar", None, "Preto Fosco", "Industrial"),
        ("CESTO-ROUPAS-TECIDO", "Cesto Organizador de Roupas Dobrável Impermeável 60L", 59.90, 21.00, 85, "Lavanderia & Quarto", "60 Litros", "Cinza Mescla", "Funcional"),
        ("DISP-SABONETE-SENSOR", "Dispensador Automático Sabonete Líquido Touchless 400ml", 79.90, 29.00, 50, "Banheiro & Higiene", None, "Branco Puro", "Moderno"),
        ("JG-AMERICANO-BOHO", "Jogo Americano Trançado Redondo 38cm Kit com 6 Peças", 64.90, 22.00, 75, "Mesa Posta", "38cm", "Palha Natural", "Boho Chic"),
        ("TRAVESSAS-PORCELANA", "Conjunto 4 Travessas Refratárias Porcelana Forno e Mesa", 149.90, 62.00, 40, "Mesa Posta", None, "Branco Neve", "Clássico")
    ],
    "toys": [
        ("TABULEIRO-CATAN", "Jogo de Tabuleiro Catan Colonizadores Estratégia", 289.90, 145.00, 25, "Jogos de Tabuleiro", "+10 anos", None, "Estratégia"),
        ("BLOCOS-CASTELO-850", "Kit Blocos de Montar Castelo Encantado 850 Peças", 199.90, 82.00, 40, "Blocos de Montar", "+6 anos", "Colorido", "Educativo"),
        ("BONECA-REBORN-48CM", "Boneca Bebê Reborn Realista 48cm com Chupeta Magnética", 319.90, 138.00, 20, "Bonecas & Acessórios", "+3 anos", "Rosa Claro", "Realismo"),
        ("CARRO-RC-4X4-OFFROAD", "Carrinho Controle Remoto 4x4 Off-Road Bateria Recarregável", 189.90, 78.00, 35, "Veículos & RC", "+8 anos", "Verde Musgo", "Aventura"),
        ("PUZZLE-1000-CIDADES", "Quebra-Cabeça 1000 Peças Paisagem Cidades do Mundo HD", 69.90, 26.00, 80, "Quebra-Cabeças", "+12 anos", "Multicolor", "Lazer"),
        ("PISTA-LOOP-360", "Pista de Corrida com Loop Duplo 360° e Disparador Turbo", 149.90, 60.00, 45, "Pistas & Ação", "+4 anos", "Laranja / Azul", "Radical"),
        ("PELUCIA-URSO-80CM", "Urso de Pelúcia Gigante 80cm Antialérgico Fofinho", 159.90, 65.00, 30, "Pelúcias", "Todas as idades", "Caramelo", "Afetivo"),
        ("MALETA-MASSINHA-18C", "Maleta Criativa com 18 Massinhas de Modelar e Formas", 59.90, 19.00, 95, "Criatividade & Arte", "+3 anos", "18 Cores", "Sensorial"),
        ("PEDAGOGICO-MONTESSORI", "Brinquedo Pedagógico Encaixe Formas e Letras em Madeira", 79.90, 28.00, 65, "Primeira Infância", "+2 anos", "Madeira Natural", "Montessori"),
        ("PATINETE-3RODAS-LED", "Patinete Infantil 3 Rodas com LED e Guidão Ajustável", 179.90, 74.00, 28, "Esporte & Ar Livre", "+3 a 8 anos", "Azul Elétrico", "Ativo"),
        ("DINO-TREX-SONS-LUZ", "Dinossauro T-Rex com Sons Articulado e Olhos de LED", 119.90, 46.00, 50, "Figuras de Ação", "+4 anos", "Verde Escuro", "Jurássico"),
        ("CASA-BONECAS-MDF", "Casa de Bonecas Madeira MDF 3 Andares com Mini Móveis", 389.90, 175.00, 15, "Casinhas & Faz de Conta", "+3 anos", "Rosa Pastel", "Criativo")
    ],
    "tech_mobile": [
        ("PELICULA-3D-PRIV", "Película de Vidro 3D Privacidade Dupla Camada iPhone/Android", 39.90, 7.50, 250, "Acessórios & Películas", "Universais", "Fumê Privacidade", "Proteção"),
        ("CAPA-MAGSAFE-AIR", "Capa Anti-Impacto MagSafe com Borda Reforçada Silicone", 59.90, 14.00, 180, "Capas & Proteção", "Vários Modelos", "Transparente Borda Preta", "Impacto"),
        ("CARREG-GAN-35W", "Carregador Turbo 35W Dual USB-C GaN Ultra Rápido Anatel", 119.90, 38.00, 120, "Carregadores & Energia", "Bivolt", "Branco Puro", "Tecnologia GaN"),
        ("CABO-TRANC-USBC-LIGHT", "Cabo Trançado Nylon USB-C para Lightning 1.8m Reforçado", 49.90, 12.00, 200, "Cabos & Conexões", "1.8 Metros", "Cinza Espacial", "Blindado"),
        ("FONE-TWS-ANC-PRO", "Fone Bluetooth TWS com Cancelamento Ativo de Ruído ANC", 249.90, 92.00, 75, "Áudio & Fones", "Sem fio", "Preto Matte", "Hi-Fi"),
        ("SUP-VEICULAR-INDUCAO", "Suporte Veicular Magnético com Carregamento por Indução 15W", 99.90, 32.00, 90, "Acessórios Automotivos", "Universal", "Preto", "Praticidade"),
        ("POWERBANK-20000-PD", "Power Bank Bateria Portátil 20.000mAh Display Digital 22.5W", 169.90, 64.00, 60, "Carregadores & Energia", "20000mAh", "Grafite", "Viagem"),
        ("TECLADO-MEC-RGB-TKL", "Teclado Mecânico Gamer TKL RGB Switch Blue Anti-Ghosting", 239.90, 98.00, 45, "Periféricos Gamers", "ABNT2", "Preto RGB", "Alta Performance"),
        ("MOUSE-GAMER-12K-DPI", "Mouse Gamer Óptico 12.800 DPI com Iluminação RGB", 129.90, 45.00, 80, "Periféricos Gamers", "Ergonômico", "Preto", "Precisão"),
        ("BASE-COOLER-NOTEBOOK", "Base Cooler Refrigerada com 6 Fans LED para Notebook até 17'", 119.90, 44.00, 55, "Informática & Suportes", "Até 17.3 pol", "Preto com LED Azul", "Refrigeração"),
        ("HEADSET-SURROUND-71", "Headset Gamer Surround 7.1 Microfone Noise Cancelling USB", 199.90, 76.00, 40, "Áudio & Fones", "Over-Ear", "Preto / Vermelho", "Gamer"),
        ("HUB-6EM1-USBC-HDMI", "Hub Adaptador 6 em 1 USB-C para HDMI 4K, 3x USB 3.0 e SD", 149.90, 52.00, 70, "Informática & Conexões", "Alumínio", "Prata Metálico", "Produtividade")
    ]
}

# =============================================================================
# BASE DE CLIENTES REALISTA ADAPTADA
# =============================================================================
CUSTOMERS_POOL = [
    ("TechCorp Informática Ltda", "12.345.678/0001-90", "J", "contato@techcorp.com.br", "(11) 98765-4321", "São Paulo", "SP"),
    ("Móveis & Ambientes Prime S/A", "98.765.432/0001-10", "J", "compras@ambientesprime.com.br", "(41) 99876-5432", "Curitiba", "PR"),
    ("Carlos Eduardo Silva", "123.456.789-00", "F", "carlos.silva@email.com", "(21) 97654-3210", "Rio de Janeiro", "RJ"),
    ("Mariana Souza Oliveira", "234.567.890-11", "F", "mariana.souza@email.com", "(31) 98877-6655", "Belo Horizonte", "MG"),
    ("Distribuidora Aliança Regional", "45.678.901/0001-22", "J", "pedidos@alianca.com.br", "(19) 99123-4567", "Campinas", "SP"),
    ("Fernanda Costa Pereira", "345.678.901-22", "F", "fernanda.costa@email.com", "(51) 98111-2233", "Porto Alegre", "RS"),
    ("Inovação & Comércio Varejo ME", "78.901.234/0001-55", "J", "financeiro@inovacaovarejo.com.br", "(47) 99444-5566", "Joinville", "SC"),
    ("Lucas Martins Rocha", "456.789.012-33", "F", "lucas.rocha@email.com", "(61) 98222-3344", "Brasília", "DF"),
    ("Juliana Lima Santos", "567.890.123-44", "F", "juliana.lima@email.com", "(71) 98333-4455", "Salvador", "BA"),
    ("Mercado Global & Eventos Eireli", "32.109.876/0001-33", "J", "atendimento@mercadoglobal.com", "(81) 99555-6677", "Recife", "PE"),
    ("Patrícia Nogueira Castro", "678.901.234-55", "F", "patricia.castro@email.com", "(11) 97123-9988", "São Paulo", "SP"),
    ("Roberto Almeida Junqueira", "789.012.345-66", "F", "roberto.junqueira@email.com", "(31) 99654-1122", "Uberlândia", "MG"),
]

# =============================================================================
# LANÇAMENTOS FINANCEIROS TÍPICOS POR NICHO
# =============================================================================
NICHE_EXPENSES = {
    "fashion": [
        ("Confecção & Tecelagem Santa Catarina", "Aquisição de Tecidos e Peças de Coleção", 2800.0, 8500.0, "Fornecedores"),
        ("Estamparia & Aviamentos Brasil", "Botões, Zíperes e Aviamentos Finos", 650.0, 2100.0, "Materia-Prima"),
        ("Aluguel Loja Conceito / Shopping", "Locação Comercial e Condomínio", 3800.0, 5200.0, "Ocupação"),
        ("Campanhas Instagram Ads & Influencers", "Marketing Digital e Parcerias", 900.0, 2400.0, "Marketing"),
        ("Logística Reversa & Envio Malas", "Fretes e Motoboys Express", 450.0, 1600.0, "Logística"),
        ("Receita Federal / Simples Nacional", "Tributos e Impostos sobre Faturamento", 1200.0, 3900.0, "Tributos")
    ],
    "furniture_appliances": [
        ("Indústria de Estofados & Móveis Paraná", "Reposição de Sofás e Mesas de Jantar", 8500.0, 24000.0, "Fornecedores"),
        ("Whirlpool / Midea Eletrodomésticos", "Faturamento Linha Branca e Refrigeradores", 12000.0, 35000.0, "Fornecedores"),
        ("Transportadora Cargas Pesadas Brasil", "Frete Frota Pesada e Carretas", 2200.0, 6800.0, "Logística"),
        ("Equipe Tercerizada de Montagem de Móveis", "Serviços Técnicos de Montagem", 1800.0, 4500.0, "Operacional"),
        ("Aluguel Pavilhão Showroom Comercial", "Locação de Grande Porte", 5500.0, 8900.0, "Ocupação"),
        ("Tributos Estaduais ICMS & Simples", "Impostos sobre Circulação de Mercadorias", 3200.0, 9500.0, "Tributos")
    ],
    "food_restaurant": [
        ("Frigorífico Carnes Nobres e Angus", "Cortes Especiais e Hambúrgueres", 3200.0, 8900.0, "Insumos & Alimentos"),
        ("Distribuidora Ambev & Cervejarias", "Barris de Chopp e Bebidas em Geral", 1800.0, 5600.0, "Bebidas"),
        ("Hortifruti & Laticínios da Serra", "Queijos, Vegetais Frescos e Molhos", 950.0, 2900.0, "Alimentação"),
        ("Embalagens Térmicas Delivery Kraft", "Caixas de Burger e Embalagens Lacradas", 680.0, 1850.0, "Embalagens"),
        ("Taxas Operacionais iFood e Plataformas", "Comissões de Delivery", 1200.0, 3800.0, "Comissões"),
        ("Gás Canalizado e Energia Elétrica", "Custos Operacionais de Cozinha", 1400.0, 2900.0, "Utilidades")
    ],
    "home_varieties": [
        ("Importadora Utilidades & Plásticos Santos", "Cargas de Organizadores e Vidros", 4200.0, 12500.0, "Fornecedores"),
        ("Fábrica de Panelas e Cerâmicas do Sul", "Lotes de Panelas Antiaderentes", 3100.0, 8900.0, "Fornecedores"),
        ("Aluguel Ponto Comercial de Calçadão", "Locação de Loja de Variedades", 3200.0, 4800.0, "Ocupação"),
        ("Caixas de Papelão e Fitas de Empacotamento", "Insumos de Expedição E-commerce", 450.0, 1400.0, "Embalagens"),
        ("Correios e Transportadoras Envios", "Fretes de Envio Shopee / ML", 1100.0, 3600.0, "Logística"),
        ("Simples Nacional e Taxas Municipais", "Impostos Fiscais", 1500.0, 4200.0, "Tributos")
    ],
    "toys": [
        ("Distribuidora Nacional de Brinquedos", "Jogos de Tabuleiro, Quebra-Cabeças e Pelúcias", 4800.0, 15000.0, "Fornecedores"),
        ("Importadora de Eletrônicos e Miniaturas RC", "Carrinhos de Controle e Pistas", 2900.0, 8600.0, "Fornecedores"),
        ("Papéis de Presente, Sacolas e Laços", "Embalagens Afetivas e de Presente", 550.0, 1750.0, "Insumos"),
        ("Aluguel Loja Shopping Center", "Locação Comercial e Fundo de Promoção", 4500.0, 7800.0, "Ocupação"),
        ("Marketing Dia das Crianças / Natal", "Campanhas Promocionais e Catálogos", 800.0, 2800.0, "Marketing"),
        ("Impostos e Tributação Fiscal", "Simples Nacional", 1600.0, 4900.0, "Tributos")
    ],
    "tech_mobile": [
        ("Distribuidora Acessórios Mobile & GaN", "Películas 3D, Carregadores e Cabos", 3500.0, 11000.0, "Fornecedores"),
        ("Importadora de Periféricos Gamers", "Teclados Mecânicos, Mouses e Headsets", 4200.0, 13500.0, "Fornecedores"),
        ("Aluguel Quiosque / Loja Tech", "Locação Ponto Comercial", 2900.0, 4600.0, "Ocupação"),
        ("Embalagens Bolha e Blisters de Proteção", "Insumos de Envio Express", 400.0, 1200.0, "Embalagens"),
        ("Taxas de Intermediação Mercado Livre / Shopee", "Comissões de Venda Online", 1400.0, 4100.0, "Comissões"),
        ("Tributos e ICMS Substituição Tributária", "Impostos sobre Eletrônicos", 1900.0, 5400.0, "Tributos")
    ]
}


def clear_operational_data():
    """Limpa tabelas operacionais preservando credenciais e configurações Bling."""
    ConditionalBag.query.delete()
    ProductReturn.query.delete()
    SellerAttendance.query.delete()
    CustomerSurvey.query.delete()
    OrderItem.query.delete()
    Order.query.delete()
    Product.query.delete()
    Customer.query.delete()
    FinancialEntry.query.delete()
    db.session.commit()


def seed_niche_demo_data(niche: str = "fashion", clear_first: bool = True):
    """
    Popula uma base completa e ultra-realista para o nicho de mercado selecionado:
    1. fashion: Moda & Vestuário (com malas condicionais, trocas, consultoras)
    2. furniture_appliances: Movelaria & Eletrodomésticos (tickets altos, montagem)
    3. food_restaurant: Lanchonete, Bar & Restaurante (delivery, mesas, combos)
    4. home_varieties: Utilidades Domésticas & Variedades (cestas amplas de itens)
    5. toys: Loja de Brinquedos & Lazer (jogos, pelúcias, presentes)
    6. tech_mobile: Artigos para Celular & Informática (acessórios, periféricos)
    """
    niche_key = niche.strip().lower() if niche else "fashion"
    if niche_key not in NICHE_METADATA:
        niche_key = "fashion"

    meta = NICHE_METADATA[niche_key]
    prod_catalog = NICHE_PRODUCTS.get(niche_key, NICHE_PRODUCTS["fashion"])
    niche_expenses = NICHE_EXPENSES.get(niche_key, NICHE_EXPENSES["fashion"])
    channels = meta["channels"]
    sellers = meta["default_sellers"]

    if clear_first:
        clear_operational_data()

    today = date.today()

    # 1. Criação dos Clientes
    created_customers = []
    for idx, (name, doc, ptype, email, phone, city, state) in enumerate(CUSTOMERS_POOL, start=101):
        c = Customer(
            bling_id=idx,
            name=name,
            document=doc,
            person_type=ptype,
            email=email,
            phone=phone,
            city=city,
            state=state,
            created_at=datetime.utcnow() - timedelta(days=random.randint(25, 180))
        )
        db.session.add(c)
        created_customers.append(c)
    db.session.commit()

    # 2. Criação dos Produtos
    created_products = []
    base_prod_id = 2001
    for prod_data in prod_catalog:
        # Tuplas podem ter 9 itens (com tamanho, cor, estilo) ou 6
        sku = prod_data[0]
        name = prod_data[1]
        price = prod_data[2]
        cost = prod_data[3]
        stock = prod_data[4]
        category = prod_data[5]
        size = prod_data[6] if len(prod_data) > 6 else None
        color = prod_data[7] if len(prod_data) > 7 else None
        style = prod_data[8] if len(prod_data) > 8 else None

        p = Product(
            bling_id=base_prod_id,
            sku=sku,
            name=name,
            price=price,
            cost=cost,
            stock=stock,
            category=category,
            size=size,
            color=color,
            style=style,
            status='A'
        )
        db.session.add(p)
        created_products.append(p)
        base_prod_id += 1
    db.session.commit()

    # 3. Criação de Pedidos e Itens (Últimos 60 dias)
    order_num = 1001
    statuses = ["Atendido", "Atendido", "Atendido", "Atendido", "Em aberto", "Cancelado"]

    # Frequência de pedidos por nicho
    orders_per_day_range = {
        "food_restaurant": (2, 6),
        "home_varieties": (2, 5),
        "tech_mobile": (2, 5),
        "toys": (1, 4),
        "fashion": (1, 4),
        "furniture_appliances": (1, 3)
    }.get(niche_key, (1, 4))

    # Formas de pagamento
    pay_methods = {
        "fashion": ["Cartão de Crédito", "Pix", "Boleto Bancário"],
        "food_restaurant": ["Pix", "Cartão de Crédito", "Cartão de Débito", "Dinheiro"],
        "furniture_appliances": ["Cartão de Crédito 10x", "Boleto Financiado", "Pix", "Transferência"],
        "home_varieties": ["Pix", "Cartão de Crédito", "Boleto Bancário", "Cartão de Débito"],
        "toys": ["Pix", "Cartão de Crédito 6x", "Boleto Bancário", "Dinheiro"],
        "tech_mobile": ["Pix", "Cartão de Crédito", "Cartão de Débito", "Link de Pagamento"]
    }.get(niche_key, ["Cartão de Crédito", "Pix", "Boleto Bancário"])

    for days_ago in range(60, -1, -1):
        order_date = today - timedelta(days=days_ago)
        daily_count = random.randint(*orders_per_day_range)

        # Restaurantes vendem mais sexta, sábado e domingo
        if niche_key == "food_restaurant" and order_date.weekday() in (4, 5, 6):
            daily_count += random.randint(2, 4)

        for _ in range(daily_count):
            cust = random.choice(created_customers)
            channel = random.choice(channels)
            status = random.choice(statuses)
            seller = random.choice(sellers)
            pay_method = random.choice(pay_methods)

            # Frete por nicho
            if niche_key == "furniture_appliances":
                shipping = random.choice([79.90, 129.90, 189.90, 249.00])
            elif niche_key == "food_restaurant":
                shipping = 0.0 if "Salão" in channel else random.choice([0.0, 7.90, 11.90, 14.90])
            else:
                shipping = random.choice([0.0, 14.90, 22.90, 34.90])

            discount = random.choice([0.0, 0.0, 10.0, 25.0]) if niche_key != "food_restaurant" else 0.0

            order = Order(
                bling_id=order_num + 50000,
                number=str(order_num),
                order_date=order_date,
                status=status,
                channel=channel,
                payment_method=pay_method,
                seller_name=seller,
                customer_id=cust.id,
                total=0.0,
                discount=discount,
                shipping=shipping
            )
            db.session.add(order)
            db.session.flush()

            # Quantidade de itens no pedido
            max_items = 4 if niche_key in ("home_varieties", "tech_mobile", "food_restaurant") else 2
            items_sample_count = random.randint(1, min(max_items, len(created_products)))
            chosen_prods = random.sample(created_products, items_sample_count)

            subtotal = 0.0
            for prod in chosen_prods:
                qty = random.randint(1, 3) if niche_key in ("food_restaurant", "home_varieties", "tech_mobile") else 1
                item_total = prod.price * qty
                subtotal += item_total

                item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id,
                    product_name=prod.name,
                    sku=prod.sku,
                    quantity=qty,
                    unit_price=prod.price,
                    cost_price=prod.cost,
                    total_price=item_total
                )
                db.session.add(item)

            order.total = max(0.0, round(subtotal - order.discount + order.shipping, 2))
            order_num += 1

    db.session.commit()

    # 4. Criação de Contas a Receber e Contas a Pagar
    fin_id = 91001

    # Contas a Receber
    for days_ago in range(45, -15, -2):
        due = today - timedelta(days=days_ago)
        is_past = due <= today
        status = 'Pago' if is_past and random.random() > 0.08 else ('Atrasado' if is_past else 'Pendente')
        pay_date = due if status == 'Pago' else None

        min_rec = 45.0 if niche_key == "food_restaurant" else (800.0 if niche_key == "furniture_appliances" else 150.0)
        max_rec = 350.0 if niche_key == "food_restaurant" else (4800.0 if niche_key == "furniture_appliances" else 1200.0)

        rec = FinancialEntry(
            bling_id=fin_id,
            entry_type='RECEBER',
            description=f"Recebimento de Vendas / {niche_key.replace('_', ' ').title()}",
            entity_name=random.choice(CUSTOMERS_POOL)[0],
            category="Vendas de Mercadorias",
            amount=round(random.uniform(min_rec, max_rec), 2),
            issue_date=due - timedelta(days=random.randint(5, 20)),
            due_date=due,
            payment_date=pay_date,
            status=status,
            payment_method=random.choice(["Pix", "Cartão de Crédito", "Boleto Bancário"])
        )
        db.session.add(rec)
        fin_id += 1

    # Contas a Pagar
    for days_ago in range(45, -20, -3):
        due = today - timedelta(days=days_ago)
        is_past = due <= today
        supplier, desc, min_v, max_v, cat = random.choice(niche_expenses)
        status = 'Pago' if is_past and random.random() > 0.06 else ('Atrasado' if is_past else 'Pendente')
        pay_date = due if status == 'Pago' else None

        pag = FinancialEntry(
            bling_id=fin_id,
            entry_type='PAGAR',
            description=desc,
            entity_name=supplier,
            category=cat,
            amount=round(random.uniform(min_v, max_v), 2),
            issue_date=due - timedelta(days=15),
            due_date=due,
            payment_date=pay_date,
            status=status,
            payment_method=random.choice(["Boleto Bancário", "Pix", "TED"])
        )
        db.session.add(pag)
        fin_id += 1

    # 5. Enriquecimento Especial para Moda (Malas Condicionais, Devoluções e Consultoria)
    if niche_key == "fashion":
        try:
            from app.services.demo_fashion_data import seed_fashion_demo_data
            seed_fashion_demo_data()
        except Exception as fe:
            pass

    # 6. Atualização das Configurações do Sistema
    Setting.set('demo_mode_active', '1')
    Setting.set('demo_cleared', '0')
    Setting.set('demo_niche_id', niche_key)
    Setting.set('demo_niche_name', meta["name"])
    Setting.set('last_sync_date', datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S'))
    Setting.set('last_sync_status', f"Base de Demonstração Ativa: {meta['name']}")
    db.session.commit()

    return {
        "success": True,
        "niche_id": niche_key,
        "niche_name": meta["name"],
        "orders_count": Order.query.count(),
        "products_count": Product.query.count(),
        "customers_count": Customer.query.count(),
        "financial_count": FinancialEntry.query.count()
    }
