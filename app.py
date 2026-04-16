from flask import Flask, render_template, request, jsonify
import xmlrpc.client

app = Flask(__name__)

# Configuración Odoo
URL = 'https://ventasatc.opendrive.cl'
DB = 'PRODUCCION'
USER = 'admin'
PASS = 'atcdrive2018'

# --- MEJORA B: REUTILIZAR LA CONEXIÓN ---
# Variables globales para almacenar la sesión y no autenticar en cada escaneo
odoo_uid = None
odoo_models = None

def get_odoo_connection():
    """Obtiene y reutiliza la conexión a Odoo para maximizar la velocidad."""
    global odoo_uid, odoo_models
    
    try:
        # Solo se autentica la primera vez (o si la sesión se pierde)
        if not odoo_uid:
            common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
            odoo_uid = common.authenticate(DB, USER, PASS, {})
            if odoo_uid:
                odoo_models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
        return odoo_uid, odoo_models
    except Exception as e:
        # En caso de error (ej. reinicio del servidor), limpiamos el uid para forzar reconexión
        odoo_uid = None
        raise e

def format_order_name(name):
    """Normaliza el nombre de la orden a SOXXXXXXX"""
    clean_name = name.strip().upper()
    if not clean_name.startswith('SO') and clean_name:
        clean_name = f"SO{clean_name}"
    return clean_name

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
def home():
    """Página principal con selección de Marketplace"""
    return render_template('home.html')

@app.route('/falabella')
def falabella():
    """Verificador estilo Falabella"""
    return render_template('falabella.html')

@app.route('/ripley')
def ripley():
    """Verificador estilo Ripley"""
    return render_template('ripley.html')

# --- LÓGICA DE NEGOCIO (API) ---

@app.route('/verify', methods=['POST'])
def verify():
    global odoo_uid
    data = request.json
    order_name = format_order_name(data.get('name', ''))
    client_ref = data.get('client_ref', '').strip()
    
    try:
        # Llamamos a nuestra función optimizada que reutiliza la sesión
        uid, models = get_odoo_connection()
        
        if not uid:
            return {"status": "error", "message": "Fallo de autenticación en Odoo."}

        # Buscamos la coincidencia exacta de Nombre y Referencia
        domain = [['name', '=', order_name], ['client_order_ref', '=', client_ref]]
        
        # --- MEJORA A: TRAER SOLO LO NECESARIO Y LIMITAR RESULTADOS ---
        orders = models.execute_kw(DB, uid, PASS, 'sale.order', 'search_read', [domain], {
            'fields': ['partner_id'],
            'limit': 1  # ¡Clave! Esto le dice a Odoo que deje de buscar en cuanto encuentre el primero
        })

        if orders:
            # orders[0]['partner_id'][1] contiene el nombre del cliente (ej: "Falabella Retail")
            return {"status": "success", "message": f"¡Coincidencia! Cliente: {orders[0]['partner_id'][1]}"}
        else:
            return {"status": "error", "message": f"No se encontró la orden {order_name} con esa referencia."}
            
    except Exception as e:
        # Si la sesión de Odoo se cerró o expiró, la reseteamos para que se renueve automáticamente en el próximo escaneo
        odoo_uid = None
        return {"status": "error", "message": f"Error de conexión: {str(e)}"}

# --- EJECUCIÓN DEL SERVIDOR ---

if __name__ == '__main__':
    # host='0.0.0.0' permite conexiones externas (Celulares, Tablets, otras PCs)
    # port=5000 es el puerto por defecto de Flask
    app.run(host='0.0.0.0', port=5000, debug=True)
