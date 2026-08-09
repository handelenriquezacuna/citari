#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-seed.py - Generador determinista de database/scripts/03-seed-data.sql.

Emite el seed completo del schema en espanol (identificadores ASCII, datos con
acentos). Sin aleatoriedad y sin datetime.now(): todas las fechas derivan de la
constante literal ANCHOR_DATE, por lo que dos ejecuciones producen bytes
identicos.

Uso:
    python3 scripts/gen-seed.py            escribe database/scripts/03-seed-data.sql
    python3 scripts/gen-seed.py --check    regenera a un archivo temporal y compara
                                           byte a byte con el archivo committeado.
                                           Imprime OK/FAIL y sale con 0/1.
"""

import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "database" / "scripts" / "03-seed-data.sql"

# Fecha ancla literal: todas las fechas del seed derivan de esta constante.
ANCHOR_DATE = date(2026, 7, 1)

# Hashes bcrypt literales ya usados por el equipo (datos de prueba, no secretos).
HASH_ADMIN123 = "$2b$12$HNf7oIJgipKcyCIEJLR1POaKhc46Oh//2IJ7eNtn/Mu5wvNC98qFe"
HASH_BOWNER123 = "$2b$12$6B3wIs./ish6IGqLCScHCet1uryH9qoa9WPGGqEzBVa47GL7kJHPe"

ROWS_PER_TABLE = 50

# ---------------------------------------------------------------------------
# Datos constantes
# ---------------------------------------------------------------------------

# tipos_negocios: (nombre, descripcion)
TIPOS_NEGOCIOS = [
    ("Barbería", "Corte y arreglo personal"),
    ("Salón de belleza", "Servicios de estilismo y belleza"),
    ("Spa", "Tratamientos de relajación y bienestar"),
    ("Veterinaria", "Servicios de salud para mascotas"),
    ("Clínica", "Atención médica general"),
    ("Consultorio", "Atención médica especializada"),
    ("Centro estético", "Tratamientos estéticos"),
    ("Odontología", "Servicios dentales"),
    ("Gimnasio", "Acondicionamiento físico"),
    ("Terapias", "Terapias alternativas"),
    ("Fisioterapia", "Rehabilitación física"),
    ("Nutrición", "Consulta nutricional"),
    ("Psicología", "Salud mental y terapia"),
    ("Quiropráctica", "Ajustes y terapia de columna"),
    ("Podología", "Cuidado de los pies"),
    ("Optometría", "Examen de la vista"),
    ("Dermatología", "Cuidado de la piel"),
    ("Peluquería canina", "Estética para mascotas"),
    ("Estudio de tatuajes", "Tatuajes y arte corporal"),
    ("Estudio de piercing", "Perforaciones corporales"),
    ("Fotografía", "Sesiones fotográficas"),
    ("Escuela de música", "Clases de instrumentos musicales"),
    ("Academia de baile", "Clases de baile"),
    ("Tutorías académicas", "Apoyo escolar personalizado"),
    ("Escuela de idiomas", "Clases de idiomas"),
    ("Autolavado", "Lavado y detallado de vehículos"),
    ("Taller mecánico", "Mantenimiento de vehículos"),
    ("Cerrajería", "Servicios de cerrajería"),
    ("Estudio de yoga", "Clases de yoga"),
    ("Estudio de pilates", "Clases de pilates"),
    ("Entrenamiento personal", "Entrenamiento uno a uno"),
    ("Masoterapia", "Masajes terapéuticos"),
    ("Acupuntura", "Medicina tradicional china"),
    ("Medicina general", "Consulta médica familiar"),
    ("Pediatría", "Atención médica infantil"),
    ("Ginecología", "Salud femenina"),
    ("Oftalmología", "Salud ocular"),
    ("Audiología", "Salud auditiva"),
    ("Laboratorio clínico", "Exámenes de laboratorio"),
    ("Radiología", "Imágenes médicas"),
    ("Sala de eventos", "Alquiler de espacios para eventos"),
    ("Catering", "Servicios de alimentación"),
    ("Floristería", "Arreglos florales"),
    ("Repostería", "Pasteles y postres por encargo"),
    ("Sastrería", "Confección y arreglos de ropa"),
    ("Zapatería", "Reparación de calzado"),
    ("Lavandería", "Lavado y planchado"),
    ("Limpieza de hogar", "Servicios de limpieza residencial"),
    ("Jardinería", "Mantenimiento de jardines"),
    ("Consultoría legal", "Asesoría jurídica"),
]

# estados_dominios: 4 reales + relleno de prueba hasta 50 (requisito R4)
ESTADOS_DOMINIOS_REALES = [
    ("pendiente", "Pendiente de aprobación"),
    ("activo", "Activo y operando"),
    ("suspendido", "Suspendido por administrador"),
    ("inactivo", "Inactivo o dado de baja"),
]

# estados_reservaciones: 5 reales + relleno de prueba hasta 50 (requisito R4)
ESTADOS_RESERVACIONES_REALES = [
    ("pendiente", "Reserva pendiente de confirmación"),
    ("confirmada", "Reserva confirmada"),
    ("cancelada", "Reserva cancelada"),
    ("completada", "Reserva completada"),
    ("reagendada", "Reserva reagendada"),
]

# superadmins reales (mismos correos y hash del seed original):
# (nombre, apellido_1, apellido_2, correo)
SUPERADMINS_REALES = [
    ("Melanie Yeonsuk", "Campos", "Arias", "melanie.campos@citari.admin"),
    ("Isaac", "Chavez", "Zumbado", "isaac.chavez@citari.admin"),
    ("Luna", "Delgado", "Durango", "luna.delgado@citari.admin"),
    ("Handel Simón", "Enriquez", "Acuña", "handel.enriquez@citari.admin"),
    ("Jeferson Andrew", "Fuentes", "García", "jeferson.fuentes@citari.admin"),
]

# Pools deterministas para los 45 superadmins de prueba (indexados, sin random).
SA_NOMBRES = [
    "Adrián", "Beatriz", "Cristopher", "Diana", "Ernesto",
    "Flor", "Gerardo", "Hannia", "Iván", "Julieta",
    "Keylor", "Lorena", "Marco", "Natalia", "Octavio",
]
SA_APELLIDOS_1 = [
    "Mora", "Vargas", "Solano", "Brenes", "Alfaro",
    "Villalobos", "Sánchez", "Castro", "Rojas",
]
SA_APELLIDOS_2 = [
    "Jiménez", "Hernández", "Picado", "Salas", "Monge", "Esquivel", "Cascante", None,
]

# dominios: (tipo_negocio_id, nombre, slug, correo, telefono, descripcion, mensaje_publico)
DOMINIOS = [
    (1, "Barbería El Colocho", "barberia-el-colocho", "info@colochocr.com", "2278-1001", "Barbería clásica en San Pedro", "Pura vida! Agendá tu cita sin filas."),
    (2, "Salón Elegance", "salon-elegance", "contacto@elegancecr.com", "2278-1002", "Salón de belleza en Escazú", "Tu estilo, nuestra pasión."),
    (3, "Spa La Garita", "spa-la-garita", "reservas@lagarita.com", "2278-1003", "Spa y masajes en Santa Ana", "Relajate con nosotros, mae."),
    (4, "Veterinaria San Jorge", "vet-san-jorge", "citas@sanveterinaria.com", "2278-1004", "Veterinaria en Moravia", "Cuidamos a su mascota como propia."),
    (5, "Clínica Santa Catalina", "clinica-santa-catalina", "info@santacatalina.com", "2278-1005", "Clínica médica en Desamparados", "Salud para toda la familia."),
    (6, "Consultorio Dra. Solís", "dra-solis", "citas@drasolis.com", "2278-1006", "Odontología general en Rohrmoser", "Tu sonrisa es nuestra prioridad."),
    (7, "Centro Estético Glow", "centro-glow", "hola@centroglow.com", "2278-1007", "Estética avanzada en Curridabat", "Descubrí tu mejor versión."),
    (8, "Odontoclínica del Valle", "odontoclinica-valle", "citas@odvcr.com", "2278-1008", "Clínica dental en Alajuela", "Tu salud bucal nos importa."),
    (9, "Fit Gym Centro", "fit-gym", "info@fitgymcr.com", "2278-1009", "Gimnasio en Heredia", "Transformá tu cuerpo."),
    (10, "Terapias Holísticas CR", "terapias-holisticas", "contacto@terapiascr.com", "2278-1010", "Terapias alternativas en Cartago", "Equilibrio para cuerpo y mente."),
    (1, "Barbería Don Chepe", "barberia-don-chepe", "chepe@donchepecr.com", "2278-1011", "Barbería tradicional en Guadalupe", "Donde los ticos se arreglan."),
    (2, "Salón Divino", "salon-divino", "info@salandivino.com", "2278-1012", "Salón y estética en San José", "Belleza con corazón tico."),
    (3, "Spa Pura Vida", "spa-pura-vida", "reservas@puracr.com", "2278-1013", "Spa con hidroterapia en Barrio Escalante", "Desconectate del estrés."),
    (4, "Veterinaria Huellitas", "vet-huellitas", "contacto@huellitascr.com", "2278-1014", "Veterinaria en Tibás", "Tu mascota merece lo mejor."),
    (1, "Barbería King", "barberia-king", "king@barberiaking.com", "2278-1015", "Barbería moderna en Hatillo", "Estilo tico con actitud."),
    (2, "Salón Santa Ana", "salon-santa-ana", "info@santaanabeauty.com", "2278-1016", "Salón de belleza en Santa Ana", "Embellecé tu día."),
    (5, "Clínica Médica Central", "clinica-medica-central", "info@cmcentral.com", "2278-1017", "Clínica en el centro de San José", "Atención médica de confianza."),
    (6, "Psicología Integral", "psicologia-integral", "citas@psiintegral.com", "2278-1018", "Consulta psicológica en Rohrmoser", "Tu salud mental es primero."),
    (9, "CrossFit Pérez Zeledón", "crossfit-perez", "info@crossfitpz.com", "2278-1019", "CrossFit y funcional en Pérez Zeledón", "Superá tus límites."),
    (3, "Spa La Sabana", "spa-la-sabana", "hola@lasabanacr.com", "2278-1020", "Spa frente al Parque Metropolitano", "Tu oasis en la ciudad."),
    (1, "Barbería El Rubio", "barberia-el-rubio", "rubio@barberiacr.com", "2278-1021", "Barbería en Zapote", "Corte y afeitado de primera."),
    (2, "Salón Mary", "salon-mary", "mary@salanmary.com", "2278-1022", "Salón de belleza en Tibás", "Tu lugar de confianza."),
    (3, "Spa Montaña Azul", "spa-montana-azul", "info@spamontana.com", "2278-1023", "Spa en las montañas de Heredia", "Un respiro natural."),
    (7, "Estética Karina", "estetica-karina", "karina@estetikcr.com", "2278-1024", "Centro de estética en Curridabat", "Destacá tu belleza natural."),
    (1, "Barbería Los Amigos", "barberia-amigos", "amigos@barberiacr.com", "2278-1025", "Barbería en San Francisco de Dos Ríos", "Llegue, está en su casa."),
    (8, "Clínica Dental San José", "dental-san-jose", "citas@dentalcr.com", "2278-1026", "Odontología en Sabana Sur", "Tu sonrisa saludable."),
    (3, "Centro de Masajes Zen", "masajes-zen", "info@zentralcr.com", "2278-1027", "Masajes y terapias en Barrio Amón", "Encontrá tu zen interior."),
    (4, "Peluquería Canina CR", "pelu-canina-cr", "hola@pelucanina.com", "2278-1028", "Estética canina en Moravia", "Tu mascota bien cuidada."),
    (9, "Gimnasio BodyFit", "gym-bodyfit", "info@bodyfitcr.com", "2278-1029", "Gimnasio en San Pedro", "Transformate con nosotros."),
    (10, "Nutrición Vida", "nutricion-vida", "citas@nutriovidacr.com", "2278-1030", "Consultorio nutricional en Heredia", "Comé rico, viví mejor."),
    (1, "Barbería El Peluquero", "barberia-peluquero", "peluquero@crbarber.com", "2278-1031", "Barbería en Alajuela centro", "Estilo clásico y moderno."),
    (2, "Uñas Perfectas", "unas-perfectas", "info@unasperfectas.com", "2278-1032", "Salón de uñas en Escazú", "Tus manos hablan por vos."),
    (3, "Spa Tropical", "spa-tropical", "reservas@tropicalcr.com", "2278-1033", "Spa en Guanacaste", "Relajación con vista al mar."),
    (4, "Veterinaria Mascotas Felices", "vet-mascotas-felices", "contacto@mascotascr.com", "2278-1034", "Veterinaria en Alajuela", "Un hogar para tu mascota."),
    (1, "Barbería Estilo", "barberia-estilo", "estilo@barberiacr.com", "2278-1035", "Barbería en Santo Domingo de Heredia", "Corte de calidad, precio justo."),
    (10, "Centro de Acupuntura", "acupuntura-cr", "citas@acupecr.com", "2278-1036", "Acupuntura y medicina china", "Equilibrio natural."),
    (4, "Veterinaria del Sur", "vet-del-sur", "info@vetsurcr.com", "2278-1037", "Veterinaria en Pérez Zeledón", "Cuidado integral para mascotas."),
    (2, "Salón Glamour", "salon-glamour", "info@glamourcr.com", "2278-1038", "Salón de belleza en Rohrmoser", "Brillo y sofisticación."),
    (1, "Barbería El Trébol", "barberia-trebol", "trebol@barberiacr.com", "2278-1039", "Barbería en Tres Ríos", "Corte con suerte."),
    (5, "Rehabilitación Física", "rehab-fisica", "citas@rehabcr.com", "2278-1040", "Fisioterapia en Curridabat", "Movete sin dolor."),
    (3, "Spa Relax Total", "spa-relax-total", "hola@relaxtotal.com", "2278-1041", "Spa en San José centro", "Desconectate del mundo."),
    (1, "Barbería y Algo Más", "barberia-algo-mas", "info@algomasbarber.com", "2278-1042", "Barbería con café en Barrio Escalante", "Corte, café y buena charla."),
    (9, "Gimnasio Femenino Fit", "gym-femenino-fit", "info@gymfitwomen.com", "2278-1043", "Gimnasio solo para mujeres", "Tu espacio, tu ritmo."),
    (8, "Odontología Especializada", "odonto-especializada", "citas@odontoespecial.com", "2278-1044", "Ortodoncia y estética dental", "Tu mejor sonrisa."),
    (10, "Terapia Ocupacional CR", "terapia-ocupacional", "info@tocupacional.com", "2278-1045", "Terapia ocupacional en Heredia", "Independencia y bienestar."),
    (1, "Barbería El Parque", "barberia-parque", "parque@barberiacr.com", "2278-1046", "Barbería frente al Parque Central", "Corte al paso."),
    (7, "Centro Estético Divine", "divine-estetica", "info@divinecr.com", "2278-1047", "Estética de lujo en Escazú", "Tratame como una diva."),
    (4, "Veterinaria 24 Horas", "vet-24-horas", "emergencias@vetcr.com", "2278-1048", "Veterinaria de emergencia en San José", "Siempre para tu mascota."),
    (2, "Salón Linda", "salon-linda", "hola@lindasalona.com", "2278-1049", "Salón de belleza en Desamparados", "Linda por dentro y por fuera."),
    (8, "Clínica Dental Premium", "dental-premium", "citas@dentalpremium.com", "2278-1050", "Clínica dental en Santa Ana", "Odontología de primera."),
]

# duenos_de_dominios: (nombre, apellido_1, apellido_2, correo, telefono)
# full_name original dividido con juicio; apellido_2 puede ser None.
DUENOS = [
    ("Martín", "Quesada", "Arias", "martin.quesada@email.com", "8877-1001"),
    ("Sofía", "Camacho", "Vindas", "sofia.camacho@email.com", "8877-1002"),
    ("Andrés", "Ramírez", None, "andres.ramirez@email.com", "8877-1003"),
    ("Gabriela", "Umaña", "Soto", "gabriela.umana@email.com", "8877-1004"),
    ("Esteban", "Chacón", None, "esteban.chacon@email.com", "8877-1005"),
    ("Daniela", "Castillo", "Mora", "daniela.castillo@email.com", "8877-1006"),
    ("Pablo", "Jiménez", None, "pablo.jimenez@email.com", "8877-1007"),
    ("Valeria", "Serrano", "Campos", "valeria.serrano@email.com", "8877-1008"),
    ("Santiago", "Víquez", None, "santiago.viquez@email.com", "8877-1009"),
    ("Camila", "Delgado", "Pineda", "camila.delgado@email.com", "8877-1010"),
    ("Felipe", "Rojas", None, "felipe.rojas@email.com", "8877-1011"),
    ("Mariana", "Porras", "Salas", "mariana.porras@email.com", "8877-1012"),
    ("Javier", "Cortés", None, "javier.cortes@email.com", "8877-1013"),
    ("Paula", "Navarro", "Brenes", "paula.navarro@email.com", "8877-1014"),
    ("Diego", "Masís", None, "diego.masis@email.com", "8877-1015"),
    ("Andrea", "Vega", "Solano", "andrea.vega@email.com", "8877-1016"),
    ("Cristian", "Herrera", None, "cristian.herrera@email.com", "8877-1017"),
    ("Renata", "Aguilar", "Chinchilla", "renata.aguilar@email.com", "8877-1018"),
    ("Manuel", "Guerrero", None, "manuel.guerrero@email.com", "8877-1019"),
    ("Fernanda", "Arce", "Villalobos", "fernanda.arce@email.com", "8877-1020"),
    ("Kevin", "Arce", None, "kevin.arce@email.com", "8877-1021"),
    ("Priscilla", "Sandí", "Rojas", "priscilla.sandi@email.com", "8877-1022"),
    ("Marcela", "Granados", None, "marcela.granados@email.com", "8877-1023"),
    ("Fabián", "Obando", "Espinoza", "fabian.obando@email.com", "8877-1024"),
    ("Tatiana", "Marín", None, "tatiana.marin@email.com", "8877-1025"),
    ("Bryan", "Zamora", "Quirós", "bryan.zamora@email.com", "8877-1026"),
    ("Hillary", "Segura", None, "hillary.segura@email.com", "8877-1027"),
    ("Geovanny", "Araya", "Fonseca", "geovanny.araya@email.com", "8877-1028"),
    ("Melany", "Bogarín", None, "melany.bogarin@email.com", "8877-1029"),
    ("Warner", "Ulloa", "Barrantes", "warner.ulloa@email.com", "8877-1030"),
    ("Rebeca", "Salazar", None, "rebeca.salazar@email.com", "8877-1031"),
    ("Allan", "Quesada", "Madrigal", "allan.quesada@email.com", "8877-1032"),
    ("Kendall", "Rodríguez", None, "kendall.rodriguez@email.com", "8877-1033"),
    ("Fiorella", "Campos", "Alpízar", "fiorella.campos@email.com", "8877-1034"),
    ("Sharon", "Calvo", None, "sharon.calvo@email.com", "8877-1035"),
    ("Yoselyn", "Murillo", "Gamboa", "yoselyn.murillo@email.com", "8877-1036"),
    ("Joseph", "Arias", None, "joseph.arias@email.com", "8877-1037"),
    ("Luis Diego", "Solís", "Carvajal", "luisdiego.solis@email.com", "8877-1038"),
    ("María Fernanda", "Mora", None, "mafe.mora@email.com", "8877-1039"),
    ("Andrés", "Fallas", "Hidalgo", "andres.fallas@email.com", "8877-1040"),
    ("Valeria", "Matamoros", None, "valeria.matamoros@email.com", "8877-1041"),
    ("Mario", "Zúñiga", "Céspedes", "mario.zuniga@email.com", "8877-1042"),
    ("Alejandra", "Corrales", None, "alejandra.corrales@email.com", "8877-1043"),
    ("Juan Pablo", "Mena", "Argüello", "jpablo.mena@email.com", "8877-1044"),
    ("Karina", "Rímolo", None, "karina.rimolo@email.com", "8877-1045"),
    ("Óscar", "Bermúdez", "Sibaja", "oscar.bermudez@email.com", "8877-1046"),
    ("Paola", "Carranza", None, "paola.carranza@email.com", "8877-1047"),
    ("Randall", "Segura", "Montero", "randall.segura@email.com", "8877-1048"),
    ("Adriana", "Ramírez", None, "adriana.ramirez@email.com", "8877-1049"),
    ("Melissa", "Cerdas", "Loría", "melissa.cerdas@email.com", "8877-1050"),
]

# clientes: (nombre, apellido_1, apellido_2, correo, telefono, notas)
CLIENTES = [
    ("Juan", "Vargas", "Mora", "juan.vargas@email.com", "8877-3001", "Cliente frecuente - prefiere sábados"),
    ("María", "Cordero", None, "maria.cordero@email.com", "8877-3002", None),
    ("Carlos", "Monge", "Salas", "carlos.monge@email.com", "8877-3003", "Alérgico a fragancias fuertes"),
    ("Ana", "Chaves", None, "ana.chaves@email.com", "8877-3004", "Prefiere atención con la misma estilista"),
    ("Pedro", "Rivera", "Solís", "pedro.rivera@email.com", "8877-3005", None),
    ("Laura", "Guillén", None, "laura.guillen@email.com", "8877-3006", "Cliente desde 2024"),
    ("José", "Pérez", "Brenes", "jose.perez@email.com", "8877-3007", None),
    ("Sofía", "Álvarez", None, "sofia.alvarez@email.com", "8877-3008", "Recomendó a 3 amigas"),
    ("Miguel", "Reyes", "Castro", "miguel.reyes@email.com", "8877-3009", "Le pagan con SINPE - dejar nota"),
    ("Carmen", "Morales", None, "carmen.morales@email.com", "8877-3010", None),
    ("Luis", "Torres", "Jiménez", "luis.torres@email.com", "8877-3011", "Siempre pide el mismo barbero"),
    ("Valentina", "Castro", None, "valentina.castro@email.com", "8877-3012", "Llega con su perro - permitir"),
    ("Andrés", "Ortiz", "Vega", "andres.ortiz@email.com", "8877-3013", None),
    ("Isabella", "Vargas", None, "isabella.vargas@email.com", "8877-3014", "Estudiante - descuento de jueves"),
    ("Diego", "Ruiz", "Alfaro", "diego.ruiz@email.com", "8877-3015", None),
    ("Camila", "Medina", None, "camila.medina@email.com", "8877-3016", "Prefiere WhatsApp para recordatorios"),
    ("Santiago", "Delgado", "Pacheco", "santiago.delgado@email.com", "8877-3017", None),
    ("Luciana", "Rojas", None, "luciana.rojas@email.com", "8877-3018", "Compra siempre el paquete completo"),
    ("Manuel", "Silva", "Araya", "manuel.silva@email.com", "8877-3019", "Le gusta pagar en efectivo"),
    ("Gabriela", "Peña", None, "gabriela.pena@email.com", "8877-3020", None),
    ("Alejandro", "Campos", "Ulate", "alejandro.campos@email.com", "8877-3021", "Atleta - masajes descontracturantes"),
    ("Mariana", "Flores", None, "mariana.flores@email.com", "8877-3022", "Lleva a sus 2 hijos también"),
    ("Francisco", "Aguilar", "Venegas", "francisco.aguilar@email.com", "8877-3023", None),
    ("Antonella", "Guzmán", None, "antonella.guzman@email.com", "8877-3024", "Celiaca - importante en notas"),
    ("Ricardo", "Mendoza", "Salazar", "ricardo.mendoza@email.com", "8877-3025", None),
    ("Josefina", "Cruz", None, "josefina.cruz@email.com", "8877-3026", "Vive en Grecia - prefiere tardes"),
    ("Eduardo", "Soto", "Marín", "eduardo.soto@email.com", "8877-3027", None),
    ("Ximena", "Pacheco", None, "ximena.pacheco@email.com", "8877-3028", "Luna de miel - dar trato especial"),
    ("Roberto", "Navarro", "Umaña", "roberto.navarro@email.com", "8877-3029", "Veterano - descuento adulto mayor"),
    ("Fernanda", "Vera", None, "fernanda.vera@email.com", "8877-3030", "Embarazada - masajes prenatal"),
    ("Kevin", "Arce", "Chacón", "kevin.arce@email.com", "8877-3031", None),
    ("Priscilla", "Sandí", None, "priscilla.sandi@email.com", "8877-3032", "Viene todos los viernes"),
    ("Esteban", "Cordero", "Vílchez", "esteban.cordero@email.com", "8877-3033", "Paga con tarjeta siempre"),
    ("Marcela", "Granados", None, "marcela.granados@email.com", "8877-3034", "Compra productos también"),
    ("Fabián", "Obando", "Rojas", "fabian.obando@email.com", "8877-3035", None),
    ("Rebeca", "Salazar", None, "rebeca.salazar@email.com", "8877-3036", "Cliente referido por Sofía"),
    ("Allan", "Quesada", "Herrera", "allan.quesada@email.com", "8877-3037", "Llega después de las 4pm"),
    ("Tatiana", "Marín", None, "tatiana.marin@email.com", "8877-3038", "Le gusta pagar en efectivo"),
    ("Bryan", "Zamora", "Picado", "bryan.zamora@email.com", "8877-3039", None),
    ("Hillary", "Segura", None, "hillary.segura@email.com", "8877-3040", "Siempre llega puntual"),
    ("Geovanny", "Araya", "Cascante", "geovanny.araya@email.com", "8877-3041", None),
    ("Melany", "Bogarín", None, "melany.bogarin@email.com", "8877-3042", "Pide cita con la misma persona"),
    ("Warner", "Ulloa", "Sequeira", "warner.ulloa@email.com", "8877-3043", "Prefiere los lunes"),
    ("Fiorella", "Campos", None, "fiorella.campos@email.com", "8877-3044", None),
    ("Kendall", "Rodríguez", "Zeledón", "kendall.rodriguez@email.com", "8877-3045", "Viene con su mamá"),
    ("Sharon", "Calvo", None, "sharon.calvo@email.com", "8877-3046", "Estudiante universitario"),
    ("Yoselyn", "Murillo", "Esquivel", "yoselyn.murillo@email.com", "8877-3047", "Pide recordatorio por SMS"),
    ("Joseph", "Arias", None, "joseph.arias@email.com", "8877-3048", "Referido por la clínica"),
    ("Luis Diego", "Solís", "Monge", "luisdiego.solis@email.com", "8877-3049", None),
    ("Mónica", "Aguilar", None, "monica.aguilar@email.com", "8877-3050", "Cliente nueva - dar bienvenida"),
]

# categorias_servicios: nombre (una por dominio, en orden)
CATEGORIAS = [
    "Cortes", "Tintura", "Masajes", "Consultas", "Estética facial",
    "Pediatría", "Limpieza", "Odontología", "Fitness", "Terapias",
    "Uñas", "Depilación", "Revisiones", "Pack pareja", "Promociones",
    "Barbería", "Maquillaje", "Spa", "Quiropráctica", "Nutrición",
    "Acupuntura", "Fisioterapia", "Odontopediatría", "Veterinaria", "Estética avanzada",
    "Cuidado capilar", "Depilación láser", "Bienestar", "Yoga", "Pilates",
    "Kinesiología", "Reflexología", "Aromaterapia", "Hidroterapia", "Fitoterapia",
    "Radiestesia", "Reiki", "Medicina general", "Pedagogía", "Logopedia",
    "Dermatología", "Tricología", "Ortodoncia", "Blanqueamiento", "Cirugía oral",
    "Periodoncia", "Endodoncia", "Implantes", "Radiografía", "Odontología general",
]

# servicios: (nombre, duracion_minutos, precio)
SERVICIOS = [
    ("Corte de cabello hombre", 30, 6000),
    ("Corte de cabello mujer", 45, 9000),
    ("Afeitado tradicional", 20, 5000),
    ("Lavado y peinado", 25, 7000),
    ("Tinte completo", 90, 35000),
    ("Manicure clásico", 40, 12000),
    ("Pedicure spa", 50, 15000),
    ("Masaje relajante", 60, 25000),
    ("Masaje descontracturante", 45, 30000),
    ("Consulta general", 30, 20000),
    ("Baño y corte mascota", 50, 15000),
    ("Corte mascota raza pequeña", 30, 10000),
    ("Limpieza facial profunda", 45, 22000),
    ("Depilación con cera", 30, 10000),
    ("Revisión dental", 20, 15000),
    ("Limpieza dental", 40, 30000),
    ("Sesión de gym dirigida", 60, 8000),
    ("Terapia de relajación", 50, 20000),
    ("Pack novia completo", 150, 75000),
    ("Corte y barba combo", 40, 10000),
    ("Peinado para fiestas", 60, 18000),
    ("Tinte con mechas", 120, 45000),
    ("Masaje con piedras calientes", 75, 35000),
    ("Consulta veterinaria general", 30, 18000),
    ("Vacunación de mascotas", 20, 12000),
    ("Corte mascota raza grande", 60, 20000),
    ("Exfoliación corporal", 50, 25000),
    ("Mascarilla facial", 30, 15000),
    ("Radiofrecuencia facial", 60, 40000),
    ("Depilación láser axilas", 30, 25000),
    ("Ortodoncia inicial", 45, 35000),
    ("Blanqueamiento dental", 90, 60000),
    ("Rutina de pesas guiada", 60, 10000),
    ("Yoga grupal", 60, 8000),
    ("Spinning", 45, 7000),
    ("Terapia psicológica", 50, 30000),
    ("Evaluación nutricional", 40, 22000),
    ("Acupuntura", 45, 20000),
    ("Reflexología", 50, 18000),
    ("Maquillaje profesional", 90, 35000),
    ("Extensiones de pestañas", 60, 25000),
    ("Uñas acrílicas", 75, 20000),
    ("Gelish", 45, 12000),
    ("Corte y diseño de cejas", 20, 5000),
    ("Tratamiento capilar", 60, 30000),
    ("Alisado permanente", 120, 55000),
    ("Hidratación facial", 45, 20000),
    ("Consulta dermatológica", 30, 25000),
    ("Limpieza de cutis", 50, 28000),
    ("Pack spa pareja", 120, 60000),
]

# localidades: nombre - la localidad i pertenece al dominio i y a la
# direccion i (direcciones i:1 con localidades en este seed).
LOCALIDADES = [
    "Sede Central", "Sucursal Escazú", "Santa Ana", "Moravia", "Desamparados",
    "Rohrmoser", "Curridabat", "Alajuela Central", "Heredia", "Cartago",
    "Guadalupe", "San José centro", "Barrio Escalante", "Tibás", "Hatillo",
    "Santa Ana Centro", "San José Centro", "Rohrmoser II", "Pérez Zeledón", "La Sabana",
    "Zapote", "Tibás Norte", "Heredia Montaña", "Curridabat Este", "Dos Ríos",
    "Sabana Sur", "Barrio Amón", "Moravia Norte", "San Pedro", "Heredia Centro",
    "Alajuela centro", "Escazú Este", "Guanacaste", "Alajuela Oeste", "Santo Domingo",
    "San José Centro Norte", "Pérez Zeledón Sur", "Rohrmoser Centro", "Tres Ríos", "Curridabat Oeste",
    "San José Central", "Barrio Escalante 2", "San José Mujeres", "Santa Ana Este", "Heredia Oeste",
    "San José Centro Sur", "Escazú Lujo", "San José 24H", "Desamparados Sur", "Santa Ana Sur",
]

# direcciones: (provincia, canton) - la distribucion territorial rota sobre
# este pool; distrito y codigo_postal se derivan deterministamente por indice.
PROVINCIAS_CANTONES = [
    ("San José", "San José"), ("San José", "Escazú"), ("San José", "Desamparados"),
    ("San José", "Puriscal"), ("San José", "Tarrazú"), ("San José", "Aserrí"),
    ("San José", "Mora"), ("San José", "Goicoechea"), ("San José", "Santa Ana"),
    ("San José", "Alajuelita"),
    ("Alajuela", "Alajuela"), ("Alajuela", "San Ramón"), ("Alajuela", "Grecia"),
    ("Alajuela", "San Mateo"), ("Alajuela", "Atenas"),
    ("Cartago", "Cartago"), ("Cartago", "Paraíso"), ("Cartago", "La Unión"),
    ("Cartago", "Jiménez"), ("Cartago", "Turrialba"),
    ("Heredia", "Heredia"), ("Heredia", "Barva"), ("Heredia", "Santo Domingo"),
    ("Heredia", "Santa Bárbara"), ("Heredia", "San Rafael"),
    ("Guanacaste", "Liberia"), ("Guanacaste", "Nicoya"), ("Guanacaste", "Santa Cruz"),
    ("Puntarenas", "Puntarenas"), ("Puntarenas", "Esparza"),
    ("Limón", "Limón"), ("Limón", "Pococí"),
]

NOTAS_CLIENTE_RESERVA = [
    "Prefiero en la mañana",
    "Antes del mediodía por favor",
    "En la tarde después de las 2",
    "Sin preferencia de horario",
    "Llamar antes de confirmar",
    "Que no sea muy temprano",
]

# Alfabeto sin caracteres ambiguos para codigos de rastreo deterministas.
CODIGO_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ"

# ---------------------------------------------------------------------------
# Helpers SQL
# ---------------------------------------------------------------------------


def sql_escape(value):
    """Escapa apostrofes para literales N'...' de T-SQL."""
    return value.replace("'", "''")


def qs(value):
    """String -> literal NVARCHAR (o NULL)."""
    if value is None:
        return "NULL"
    return "N'" + sql_escape(value) + "'"


def qdate(d):
    return "'" + d.isoformat() + "'"


def qdt(x):
    return "'" + x.strftime("%Y-%m-%dT%H:%M:%S") + "'"


def qtime(hh, mm):
    return "'{:02d}:{:02d}'".format(hh, mm)


def qbit(b):
    return "1" if b else "0"


def qmoney(n):
    return "{:.2f}".format(n)


def emit_insert(lines, table, cols, rows):
    """Emite un INSERT multi-fila + PRINT de progreso uniforme."""
    assert len(rows) == ROWS_PER_TABLE, f"{table}: {len(rows)} filas (se esperaban {ROWS_PER_TABLE})"
    lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES")
    for j, row in enumerate(rows):
        end = "," if j < len(rows) - 1 else ";"
        lines.append("    (" + ", ".join(row) + ")" + end)
    lines.append(f"PRINT '[03-seed-data] tabla {table} ... OK';")
    lines.append("GO")
    lines.append("")


# ---------------------------------------------------------------------------
# Derivaciones deterministas (fechas, horarios, bloques)
# ---------------------------------------------------------------------------


def bloque_de(i):
    """Bloque i (1..50): fecha y rango horario coherentes con el servicio i."""
    fecha = ANCHOR_DATE + timedelta(days=1 + ((i - 1) % 14))
    hora = 8 + ((i - 1) % 8)          # 08:00 .. 15:00
    minuto = 30 if i % 2 == 0 else 0  # alterna en punto / y media
    inicio = datetime(fecha.year, fecha.month, fecha.day, hora, minuto)
    duracion = SERVICIOS[i - 1][1]
    final = inicio + timedelta(minutes=duracion)
    return fecha, inicio, final


def horario_de(i):
    """Horario i (1..50): dia 0-6; domingo cerrado; turnos manana/tarde."""
    dia = (i - 1) % 7
    if dia == 0:
        return dia, None, None, True
    turno = i % 3
    if turno == 0:
        return dia, (8, 0), (17, 0), False   # jornada completa
    if turno == 1:
        return dia, (7, 0), (12, 0), False   # turno manana
    return dia, (13, 0), (18, 0), False      # turno tarde


def direccion_de(i):
    """Direccion i (1..50): provincia/canton rotan sobre el pool; distrito y
    codigo_postal se derivan del indice, sin aleatoriedad."""
    provincia, canton = PROVINCIAS_CANTONES[(i - 1) % len(PROVINCIAS_CANTONES)]
    vuelta = (i - 1) // len(PROVINCIAS_CANTONES)
    distrito = f"{canton} Centro" if vuelta == 0 else f"{canton} Distrito {vuelta + 1}"
    codigo_postal = f"{10000 + i}"
    return provincia, canton, distrito, codigo_postal


def codigo_rastreo(i):
    a = CODIGO_ALFABETO[(i * 5) % len(CODIGO_ALFABETO)]
    b = CODIGO_ALFABETO[(i * 11) % len(CODIGO_ALFABETO)]
    c = CODIGO_ALFABETO[(i * 17) % len(CODIGO_ALFABETO)]
    return f"CITARI-{a}{b}{c}{i:02d}"


# ---------------------------------------------------------------------------
# Generacion
# ---------------------------------------------------------------------------


def build_sql():
    lines = []
    lines.append("-- 03-seed-data.sql")
    lines.append("-- Proyecto: Citari")
    lines.append("-- Contenido: datos de prueba (50 registros por tabla, 24 tablas)")
    lines.append("-- Requiere una base de datos recien creada: los IDs IDENTITY")
    lines.append("-- inician en 1 y las llaves foraneas se emiten como literales 1..50.")
    lines.append("")
    lines.append("USE citari;")
    lines.append("GO")
    lines.append("")
    lines.append("SET NOCOUNT ON;")
    lines.append("GO")
    lines.append("")

    # -- tipos_negocios ------------------------------------------------------
    rows = [[qs(n), qs(d), "1"] for (n, d) in TIPOS_NEGOCIOS]
    emit_insert(lines, "tipos_negocios", ["nombre", "descripcion", "activo"], rows)

    # -- estados_dominios ----------------------------------------------------
    rows = [[qs(n), qs(d)] for (n, d) in ESTADOS_DOMINIOS_REALES]
    for n in range(len(ESTADOS_DOMINIOS_REALES) + 1, ROWS_PER_TABLE + 1):
        rows.append([qs(f"estado_demo_{n:02d}"), qs(f"Estado de dominio de prueba {n} (relleno para R4)")])
    emit_insert(lines, "estados_dominios", ["nombre", "descripcion"], rows)

    # -- estados_reservaciones -----------------------------------------------
    rows = [[qs(n), qs(d)] for (n, d) in ESTADOS_RESERVACIONES_REALES]
    for n in range(len(ESTADOS_RESERVACIONES_REALES) + 1, ROWS_PER_TABLE + 1):
        rows.append([qs(f"estado_reserva_demo_{n:02d}"), qs(f"Estado de reservación de prueba {n} (relleno para R4)")])
    emit_insert(lines, "estados_reservaciones", ["nombre", "descripcion"], rows)

    # -- superadmins: 5 reales + 45 de prueba (sin correo: normalizado) ------
    rows = []
    superadmin_correos = []
    for (nom, ap1, ap2, correo) in SUPERADMINS_REALES:
        rows.append([qs(nom), qs(ap1), qs(ap2), qs(HASH_ADMIN123), "1"])
        superadmin_correos.append(correo)
    for i in range(6, ROWS_PER_TABLE + 1):
        idx = i - 6
        nom = SA_NOMBRES[idx % len(SA_NOMBRES)]
        ap1 = SA_APELLIDOS_1[idx % len(SA_APELLIDOS_1)]
        ap2 = SA_APELLIDOS_2[idx % len(SA_APELLIDOS_2)]
        correo = f"superadmin{i:02d}@citari.local"
        rows.append([qs(nom), qs(ap1), qs(ap2), qs(HASH_ADMIN123), "1"])
        superadmin_correos.append(correo)
    emit_insert(
        lines, "superadmins",
        ["nombre", "apellido_1", "apellido_2", "contrasena_encriptada", "activo"],
        rows,
    )

    # -- superadmins_correos (correo i -> superadmin i, 1FN) -----------------
    rows = [[str(i), qs(correo)] for i, correo in enumerate(superadmin_correos, start=1)]
    emit_insert(lines, "superadmins_correos", ["superadmin_id", "correo"], rows)

    # -- dominios (estado 2 = activo; sin correo/telefono: normalizados) ----
    rows = []
    for (tipo, nombre, slug, correo, tel, desc, msg) in DOMINIOS:
        rows.append([str(tipo), "2", qs(nombre), qs(slug), qs(desc), "NULL", qs(msg), "1"])
    emit_insert(
        lines, "dominios",
        ["tipo_negocio_id", "dominio_estado_id", "nombre", "slug",
         "descripcion", "logo_url", "mensaje_publico", "activo"],
        rows,
    )

    # -- dominios_correos / dominios_telefonos (1:N por dominio, 1FN) -------
    rows = [[str(i), qs(correo)] for i, (_, _, _, correo, _, _, _) in enumerate(DOMINIOS, start=1)]
    emit_insert(lines, "dominios_correos", ["dominio_id", "correo"], rows)

    rows = [[str(i), qs(tel)] for i, (_, _, _, _, tel, _, _) in enumerate(DOMINIOS, start=1)]
    emit_insert(lines, "dominios_telefonos", ["dominio_id", "telefono"], rows)

    # -- duenos_de_dominios (dueno i -> dominio i; sin correo/telefono) -----
    rows = []
    for i, (nom, ap1, ap2, correo, tel) in enumerate(DUENOS, start=1):
        rows.append([str(i), qs(nom), qs(ap1), qs(ap2), qs(HASH_BOWNER123), "1"])
    emit_insert(
        lines, "duenos_de_dominios",
        ["dominio_id", "nombre", "apellido_1", "apellido_2",
         "contrasena_encriptada", "activo"],
        rows,
    )

    # -- duenos_de_dominios_correos / _telefonos (1:N por dueno, 1FN) -------
    rows = [[str(i), qs(correo)] for i, (_, _, _, correo, _) in enumerate(DUENOS, start=1)]
    emit_insert(lines, "duenos_de_dominios_correos", ["dueno_id", "correo"], rows)

    rows = [[str(i), qs(tel)] for i, (_, _, _, _, tel) in enumerate(DUENOS, start=1)]
    emit_insert(lines, "duenos_de_dominios_telefonos", ["dueno_id", "telefono"], rows)

    # -- clientes (cliente i -> dominio i; sin correo/telefono) --------------
    rows = []
    for i, (nom, ap1, ap2, correo, tel, notas) in enumerate(CLIENTES, start=1):
        rows.append([str(i), qs(nom), qs(ap1), qs(ap2), qs(notas)])
    emit_insert(
        lines, "clientes",
        ["dominio_id", "nombre", "apellido_1", "apellido_2", "notas"],
        rows,
    )

    # -- clientes_correos / clientes_telefonos (1:N por cliente, 1FN) -------
    rows = [[str(i), qs(correo)] for i, (_, _, _, correo, _, _) in enumerate(CLIENTES, start=1)]
    emit_insert(lines, "clientes_correos", ["cliente_id", "correo"], rows)

    rows = [[str(i), qs(tel)] for i, (_, _, _, _, tel, _) in enumerate(CLIENTES, start=1)]
    emit_insert(lines, "clientes_telefonos", ["cliente_id", "telefono"], rows)

    # -- categorias_servicios (categoria i -> dominio i) ---------------------
    rows = []
    for i, nombre in enumerate(CATEGORIAS, start=1):
        rows.append([str(i), qs(nombre), qs(f"Categoría de {nombre}"), "1"])
    emit_insert(
        lines, "categorias_servicios",
        ["dominio_id", "nombre", "descripcion", "activo"],
        rows,
    )

    # -- servicios (servicio i -> dominio i, categoria i) --------------------
    rows = []
    for i, (nombre, dur, precio) in enumerate(SERVICIOS, start=1):
        rows.append([str(i), str(i), qs(nombre), qs(f"Servicio de {nombre}"),
                     str(dur), qmoney(precio), "1", "1"])
    emit_insert(
        lines, "servicios",
        ["dominio_id", "categoria_id", "nombre", "descripcion",
         "duracion_minutos", "precio", "mostrar_precio", "activo"],
        rows,
    )

    # -- direcciones (direccion i -> localidad i, catalogo territorial) -----
    rows = []
    for i in range(1, ROWS_PER_TABLE + 1):
        provincia, canton, distrito, cpostal = direccion_de(i)
        rows.append([qs(provincia), qs(canton), qs(distrito), qs(cpostal)])
    emit_insert(lines, "direcciones", ["provincia", "canton", "distrito", "codigo_postal"], rows)

    # -- localidades (localidad i -> dominio i, direccion i, sede principal) -
    rows = []
    for i, nombre in enumerate(LOCALIDADES, start=1):
        rows.append([str(i), str(i), qs(nombre), "1", "1"])
    emit_insert(
        lines, "localidades",
        ["dominio_id", "direccion_id", "nombre", "principal", "activo"],
        rows,
    )

    # -- localidades_telefonos (telefono i -> localidad i, 1FN) --------------
    rows = []
    for i in range(1, ROWS_PER_TABLE + 1):
        tel = "2256-{:04d}".format(500 + i)
        rows.append([str(i), qs(tel)])
    emit_insert(lines, "localidades_telefonos", ["localidad_id", "telefono"], rows)

    # -- horarios (horario i -> dominio i, localidad i) ----------------------
    rows = []
    for i in range(1, ROWS_PER_TABLE + 1):
        dia, apertura, cierre, cerrado = horario_de(i)
        rows.append([
            str(i), str(i), str(dia),
            qtime(*apertura) if apertura else "NULL",
            qtime(*cierre) if cierre else "NULL",
            qbit(cerrado),
        ])
    emit_insert(
        lines, "horarios",
        ["dominio_id", "localidad_id", "dia_semana", "hora_apertura", "hora_cerrado", "cerrado"],
        rows,
    )

    # -- bloques_de_disponibilidad (bloque i -> dominio i, localidad i) ------
    rows = []
    for i in range(1, ROWS_PER_TABLE + 1):
        fecha, inicio, final = bloque_de(i)
        rows.append([str(i), str(i), qdate(fecha), qdt(inicio), qdt(final), "1"])
    emit_insert(
        lines, "bloques_de_disponibilidad",
        ["dominio_id", "localidad_id", "fecha_de_bloque", "fecha_inicio", "fecha_final", "activo"],
        rows,
    )

    # -- reservaciones (reserva i: mismo dominio en cliente/servicio/localidad/
    # -- bloque; fechas identicas a las del bloque i) -------------------------
    rows = []
    estado_cancelada = 1 + [n for n, _ in ESTADOS_RESERVACIONES_REALES].index("cancelada")
    for i in range(1, ROWS_PER_TABLE + 1):
        _, inicio, final = bloque_de(i)
        estado = 1 + ((i - 1) % len(ESTADOS_RESERVACIONES_REALES))
        nota_cli = NOTAS_CLIENTE_RESERVA[(i - 1) % len(NOTAS_CLIENTE_RESERVA)]
        nota_int = "Cliente frecuente, dar seguimiento" if i % 7 == 0 else None
        # Reservas canceladas: bloque liberado (FK NULL), igual que hace
        # tr_liberar_bloque_al_cancelar en runtime. El seed inserta directo
        # y no dispara ese trigger (es de UPDATE); sin esto, el bloque queda
        # retenido por el indice unico filtrado y reservarlo daria conflicto.
        bloque = "NULL" if estado == estado_cancelada else str(i)
        rows.append([str(i), str(i), str(i), str(i), bloque, str(estado),
                     qdt(inicio), qdt(final), qs(nota_cli), qs(nota_int)])
    emit_insert(
        lines, "reservaciones",
        ["dominio_id", "cliente_id", "servicio_id", "localidad_id",
         "bloque_disponibilidad_id", "estado_reservacion_id",
         "fecha_inicio", "fecha_final", "nota_cliente", "nota_interna"],
        rows,
    )

    # -- codigos_de_rastreos (codigo i -> reserva i) --------------------------
    rows = []
    for i in range(1, ROWS_PER_TABLE + 1):
        _, inicio, _ = bloque_de(i)
        expira = inicio + timedelta(days=30)
        rows.append([str(i), qs(codigo_rastreo(i)), qdt(expira), "1"])
    emit_insert(
        lines, "codigos_de_rastreos",
        ["reserva_id", "codigo_rastreo", "expira_en", "activo"],
        rows,
    )

    # -- registros (auditoria: creacion de cada dominio por su dueno) --------
    rows = []
    for i in range(1, ROWS_PER_TABLE + 1):
        nombre_dominio = DOMINIOS[i - 1][1]
        rows.append([str(i), str(i), "NULL", qs("dominio_creado"), qs("dominios"),
                     str(i), "NULL", qs(f"Negocio creado: {nombre_dominio}")])
    emit_insert(
        lines, "registros",
        ["dominio_id", "dueno_id", "superadmin_id", "accion", "nombre_entidad",
         "entidad_id", "valor_anterior", "nuevo_valor"],
        rows,
    )

    lines.append("PRINT '[03-seed-data] 24/24 tablas pobladas';")
    lines.append("GO")
    lines.append("")
    return "\n".join(lines)


def main():
    content = build_sql()
    data = content.encode("utf-8-sig")  # UTF-8 con BOM

    if "--check" in sys.argv[1:]:
        tmp = Path(tempfile.gettempdir()) / "gen-seed-check-03-seed-data.sql"
        tmp.write_bytes(data)
        try:
            actual = OUTPUT_PATH.read_bytes()
        except FileNotFoundError:
            print(f"[gen-seed] check {OUTPUT_PATH.name} ... FAIL (archivo no existe)")
            sys.exit(1)
        if actual == tmp.read_bytes():
            print(f"[gen-seed] check {OUTPUT_PATH.name} ... OK")
            sys.exit(0)
        print(f"[gen-seed] check {OUTPUT_PATH.name} ... FAIL (difiere del generador)")
        sys.exit(1)

    OUTPUT_PATH.write_bytes(data)
    print(f"[gen-seed] generado {OUTPUT_PATH.relative_to(REPO_ROOT)} (24 tablas, {24 * ROWS_PER_TABLE} filas) ... OK")


if __name__ == "__main__":
    main()
