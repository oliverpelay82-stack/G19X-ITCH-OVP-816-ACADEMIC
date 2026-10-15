--
-- PostgreSQL database dump
--


-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: bitacora_inmutable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.bitacora_inmutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RAISE EXCEPTION 'bitacora_auditoria es inmutable: operación % no permitida (RF-27)', TG_OP;
    END;
    $$;


--
-- Name: dictamen_protegido(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dictamen_protegido() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'dictamenes_auditoria: los dictámenes no se eliminan (RN-04)';
        END IF;
        IF OLD.revisado_por_humano THEN
            RAISE EXCEPTION 'dictamenes_auditoria: el dictamen % ya fue ratificado y es definitivo', OLD.id;
        END IF;
        IF NOT NEW.revisado_por_humano
           OR NEW.documento_id IS DISTINCT FROM OLD.documento_id
           OR NEW.expediente_id IS DISTINCT FROM OLD.expediente_id
           OR NEW.estatus_preliminar IS DISTINCT FROM OLD.estatus_preliminar
           OR NEW.origen IS DISTINCT FROM OLD.origen
           OR NEW.nivel_confianza IS DISTINCT FROM OLD.nivel_confianza
           OR NEW.requiere_revision_humana IS DISTINCT FROM OLD.requiere_revision_humana
           OR NEW.vigencia_resultado IS DISTINCT FROM OLD.vigencia_resultado
           OR NEW.tipo_documento_detectado IS DISTINCT FROM OLD.tipo_documento_detectado
           OR NEW.rfc_detectado IS DISTINCT FROM OLD.rfc_detectado
           OR NEW.match_titular IS DISTINCT FROM OLD.match_titular
           OR NEW.fecha_emision_extraida IS DISTINCT FROM OLD.fecha_emision_extraida
           OR NEW.fecha_vencimiento_extraida IS DISTINCT FROM OLD.fecha_vencimiento_extraida
           OR NEW.modelo_utilizado IS DISTINCT FROM OLD.modelo_utilizado
           OR NEW.reglas_aplicadas::text IS DISTINCT FROM OLD.reglas_aplicadas::text
           OR NEW.observaciones::text IS DISTINCT FROM OLD.observaciones::text
           OR NEW.representacion_legal::text IS DISTINCT FROM OLD.representacion_legal::text
           OR NEW.version_lectura IS DISTINCT FROM OLD.version_lectura
           OR NEW.version_instrucciones IS DISTINCT FROM OLD.version_instrucciones
           OR NEW.qr_sat::text IS DISTINCT FROM OLD.qr_sat::text
           OR NEW.version_catalogo IS DISTINCT FROM OLD.version_catalogo
           OR NEW.version_reglas_tipo IS DISTINCT FROM OLD.version_reglas_tipo
           OR NEW.nombre_documento_real IS DISTINCT FROM OLD.nombre_documento_real
           OR NEW.hash_sha256 IS DISTINCT FROM OLD.hash_sha256
           OR NEW.creado_en IS DISTINCT FROM OLD.creado_en THEN
            RAISE EXCEPTION 'dictamenes_auditoria: solo la ratificación humana puede modificar un dictamen (RN-05)';
        END IF;
        RETURN NEW;
    END;
    $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bitacora_auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bitacora_auditoria (
    id character varying(36) NOT NULL,
    evento character varying(40) NOT NULL,
    expediente_id character varying(36),
    documento_id character varying(36),
    dictamen_id character varying(36),
    usuario character varying(150) NOT NULL,
    ip_origen character varying(45),
    detalle json NOT NULL,
    creado_en timestamp without time zone NOT NULL,
    secuencia bigint,
    hash_anterior character varying(64),
    hash_evento character varying(64)
);


--
-- Name: dictamenes_auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dictamenes_auditoria (
    id character varying(36) NOT NULL,
    documento_id character varying(36) NOT NULL,
    expediente_id character varying(36) NOT NULL,
    estatus character varying(20) NOT NULL,
    estatus_preliminar character varying(20) NOT NULL,
    origen character varying(30) NOT NULL,
    nivel_confianza double precision,
    requiere_revision_humana boolean NOT NULL,
    reglas_aplicadas json NOT NULL,
    vigencia_resultado character varying(30),
    observaciones json NOT NULL,
    tipo_documento_detectado character varying(50),
    rfc_detectado character varying(13),
    match_titular boolean,
    fecha_emision_extraida date,
    fecha_vencimiento_extraida date,
    modelo_utilizado character varying(100),
    representacion_legal json,
    version_lectura character varying(160),
    version_instrucciones character varying(40),
    qr_sat json,
    version_catalogo character varying(20),
    version_reglas_tipo character varying(20),
    nombre_documento_real character varying(200),
    hash_sha256 character varying(64) NOT NULL,
    revisado_por_humano boolean NOT NULL,
    justificacion_humana text,
    revisado_por character varying(150),
    revisado_en timestamp without time zone,
    creado_en timestamp without time zone NOT NULL,
    CONSTRAINT ck_dictamenes_auditoria_estatus CHECK (((estatus)::text = ANY ((ARRAY['CONFORME'::character varying, 'NO_CONFORME'::character varying, 'EN_REVISION'::character varying])::text[]))),
    CONSTRAINT ck_dictamenes_auditoria_estatus_preliminar CHECK (((estatus_preliminar)::text = ANY ((ARRAY['CONFORME'::character varying, 'NO_CONFORME'::character varying, 'EN_REVISION'::character varying])::text[])))
);


--
-- Name: documentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos (
    id character varying(36) NOT NULL,
    expediente_id character varying(36) NOT NULL,
    tipo_documento character varying(50) NOT NULL,
    nombre_archivo_original character varying(255) NOT NULL,
    ruta_almacenamiento character varying(500) NOT NULL,
    hash_sha256 character varying(64) NOT NULL,
    procesamiento_diferido json,
    senales_pdf json,
    tamanio_bytes bigint NOT NULL,
    mime_type character varying(100) NOT NULL,
    estado_integridad character varying(20) DEFAULT 'INTEGRO'::character varying NOT NULL,
    creado_en timestamp without time zone NOT NULL,
    CONSTRAINT ck_documentos_estado_integridad CHECK (((estado_integridad)::text = ANY ((ARRAY['INTEGRO'::character varying, 'ALTERADO'::character varying])::text[]))),
    CONSTRAINT ck_documentos_tipo_documento CHECK (((tipo_documento)::text ~ '^[A-Z][A-Z0-9_]{1,49}$'::text))
);


--
-- Name: expediente_asignaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expediente_asignaciones (
    id character varying(36) NOT NULL,
    expediente_id character varying(36) NOT NULL,
    usuario_id character varying(36) NOT NULL,
    asignado_por character varying(150) NOT NULL,
    creado_en timestamp without time zone NOT NULL
);


--
-- Name: expedientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expedientes (
    id character varying(36) NOT NULL,
    titular_id character varying(36) NOT NULL,
    codigo_expediente character varying(50) NOT NULL,
    tipo_expediente character varying(20) DEFAULT 'CORPORATIVO'::character varying NOT NULL,
    nombre character varying(150),
    estado_cumplimiento character varying(30) NOT NULL,
    porcentaje_completitud numeric(5,2) NOT NULL,
    creado_en timestamp without time zone,
    actualizado_en timestamp without time zone NOT NULL,
    CONSTRAINT ck_expedientes_estado_cumplimiento CHECK (((estado_cumplimiento)::text = ANY ((ARRAY['CONFORME'::character varying, 'EN_REVISION'::character varying, 'NO_CONFORME'::character varying])::text[]))),
    CONSTRAINT ck_expedientes_tipo_expediente CHECK (((tipo_expediente)::text = ANY ((ARRAY['JURIDICO'::character varying, 'CORPORATIVO'::character varying, 'REGULATORIO'::character varying])::text[])))
);


--
-- Name: parametros_sistema; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parametros_sistema (
    clave character varying(50) NOT NULL,
    valor json NOT NULL,
    actualizado_en timestamp without time zone NOT NULL,
    actualizado_por character varying(150)
);


--
-- Name: reglas_validacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reglas_validacion (
    id character varying(36) NOT NULL,
    codigo_regla character varying(50) NOT NULL,
    nombre_regla character varying(150) NOT NULL,
    familia_regla character varying(10) NOT NULL,
    descripcion text NOT NULL,
    severidad character varying(20) NOT NULL,
    accion character varying(255) NOT NULL,
    tipo_documento character varying(50),
    documento_obligatorio boolean NOT NULL,
    tipo_expediente character varying(20),
    documento_principal character varying(50),
    dias_maximos_vigencia integer,
    activo boolean NOT NULL,
    creado_en timestamp without time zone NOT NULL,
    CONSTRAINT ck_reglas_validacion_familia_regla CHECK (((familia_regla)::text = ANY ((ARRAY['RIE'::character varying, 'RCV'::character varying, 'RSC'::character varying, 'RDS'::character varying])::text[]))),
    CONSTRAINT ck_reglas_validacion_severidad CHECK (((severidad)::text = ANY ((ARRAY['CRITICA'::character varying, 'ALTA'::character varying, 'MEDIA_ALTA'::character varying, 'MEDIA'::character varying])::text[]))),
    CONSTRAINT ck_reglas_validacion_tipo_expediente CHECK (((tipo_expediente IS NULL) OR ((tipo_expediente)::text = ANY ((ARRAY['JURIDICO'::character varying, 'CORPORATIVO'::character varying, 'REGULATORIO'::character varying])::text[]))))
);


--
-- Name: titulares_expediente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.titulares_expediente (
    id character varying(36) NOT NULL,
    rfc character varying(13) NOT NULL,
    razon_social character varying(200) NOT NULL,
    tipo_persona character varying(10) NOT NULL,
    categoria character varying(50) NOT NULL,
    creado_en timestamp without time zone NOT NULL
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id character varying(36) NOT NULL,
    email character varying(150) NOT NULL,
    password_hash character varying(255) NOT NULL,
    nombre_completo character varying(150) NOT NULL,
    rol character varying(30) NOT NULL,
    activo boolean NOT NULL,
    creado_en timestamp without time zone NOT NULL,
    debe_cambiar_contrasena boolean NOT NULL,
    intentos_fallidos integer NOT NULL,
    bloqueado_hasta timestamp without time zone,
    ultimo_acceso timestamp without time zone,
    mfa_secreto character varying(64),
    mfa_habilitado boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_usuarios_rol CHECK (((rol)::text = ANY ((ARRAY['ADMIN'::character varying, 'VALIDADOR'::character varying, 'AUDITOR'::character varying, 'CONSULTA'::character varying])::text[])))
);


--
-- Data for Name: bitacora_auditoria; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bitacora_auditoria (id, evento, expediente_id, documento_id, dictamen_id, usuario, ip_origen, detalle, creado_en, secuencia, hash_anterior, hash_evento) FROM stdin;
3bfc2fe6-8fd1-4b2f-ae21-fe00db7b3330	SELLO_GENESIS	\N	\N	\N	SISTEMA	\N	{"eventos_previos": 0, "huella_historial_previo": "0000000000000000000000000000000000000000000000000000000000000000", "desde": null, "hasta": null, "algoritmo": "SHA-256 del JSON can\\u00f3nico (claves ordenadas, UTF-8, sin espacios)"}	2026-10-15 21:54:01.840737	1	0000000000000000000000000000000000000000000000000000000000000000	c0a3c141026bea9273058f217b90cb0ae470cf1c1fdb2dde9adf390066a613b5
a6a475ab-5e8e-4c9e-9c98-2dad4eb30be6	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "0b50e554-b2c7-4be1-b371-a366ffa024ba", "email": "admin@example.com", "nombre_completo": "Administraci\\u00f3n (demostraci\\u00f3n)", "rol": "ADMIN", "origen": "DEMOSTRACION"}	2026-10-15 21:54:01.845303	2	c0a3c141026bea9273058f217b90cb0ae470cf1c1fdb2dde9adf390066a613b5	09d01aed06736c7a32d281cfb9cd3322bf6dfa740c27e54b0b7aa87b849050d0
08a8660e-43ab-4b06-9e8f-37d6e8c8bbc1	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "d6f51d1b-fb16-4536-b61b-19a62858e448", "email": "validador@example.com", "nombre_completo": "Validaci\\u00f3n (demostraci\\u00f3n)", "rol": "VALIDADOR", "origen": "DEMOSTRACION"}	2026-10-15 21:54:02.098688	3	09d01aed06736c7a32d281cfb9cd3322bf6dfa740c27e54b0b7aa87b849050d0	98c725f27dec5e408fee2c341ea28cc7b8d3eb53fd4a53072ed34cefbc9e156a
83ef758e-6dc4-44f6-8b7d-5fdd61405c57	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "ffa30ec9-b694-4cad-9f83-67c7106afb14", "email": "auditor@example.com", "nombre_completo": "Auditor\\u00eda (demostraci\\u00f3n)", "rol": "AUDITOR", "origen": "DEMOSTRACION"}	2026-10-15 21:54:02.35744	4	98c725f27dec5e408fee2c341ea28cc7b8d3eb53fd4a53072ed34cefbc9e156a	55a776a673c4b3e24d692f1f3c5783f214944b41431acf9d552dad9ee95a1065
f9422615-3a39-45a0-b07b-0d5994e3339e	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "e8eb0290-3870-430b-b372-0f694bbca643", "email": "consulta@example.com", "nombre_completo": "Consulta (demostraci\\u00f3n)", "rol": "CONSULTA", "origen": "DEMOSTRACION"}	2026-10-15 21:54:02.61798	5	55a776a673c4b3e24d692f1f3c5783f214944b41431acf9d552dad9ee95a1065	d08afe21379dd5fbfcd6feb5c31efda4a567fe1ea4574c4c1220398ee003d26a
\.


--
-- Data for Name: dictamenes_auditoria; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dictamenes_auditoria (id, documento_id, expediente_id, estatus, estatus_preliminar, origen, nivel_confianza, requiere_revision_humana, reglas_aplicadas, vigencia_resultado, observaciones, tipo_documento_detectado, rfc_detectado, match_titular, fecha_emision_extraida, fecha_vencimiento_extraida, modelo_utilizado, representacion_legal, version_lectura, version_instrucciones, qr_sat, version_catalogo, version_reglas_tipo, nombre_documento_real, hash_sha256, revisado_por_humano, justificacion_humana, revisado_por, revisado_en, creado_en) FROM stdin;
\.


--
-- Data for Name: documentos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.documentos (id, expediente_id, tipo_documento, nombre_archivo_original, ruta_almacenamiento, hash_sha256, procesamiento_diferido, senales_pdf, tamanio_bytes, mime_type, estado_integridad, creado_en) FROM stdin;
\.


--
-- Data for Name: expediente_asignaciones; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.expediente_asignaciones (id, expediente_id, usuario_id, asignado_por, creado_en) FROM stdin;
\.


--
-- Data for Name: expedientes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.expedientes (id, titular_id, codigo_expediente, tipo_expediente, nombre, estado_cumplimiento, porcentaje_completitud, creado_en, actualizado_en) FROM stdin;
385b9a9e-ce7b-4091-a6d7-bf1a2a043726	b99b85e0-0040-4d3d-9f9a-a7f36f1e7d43	EXP-BIM980101XYZ-001	CORPORATIVO	\N	EN_REVISION	0.00	2026-10-15 21:53:59.926693	2026-10-15 21:53:59.926693
\.


--
-- Data for Name: parametros_sistema; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.parametros_sistema (clave, valor, actualizado_en, actualizado_por) FROM stdin;
\.


--
-- Data for Name: reglas_validacion; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.reglas_validacion (id, codigo_regla, nombre_regla, familia_regla, descripcion, severidad, accion, tipo_documento, documento_obligatorio, tipo_expediente, documento_principal, dias_maximos_vigencia, activo, creado_en) FROM stdin;
a41c13fb-731d-4951-9d8a-acccd911b546	RIE-01	Completitud de Expediente	RIE	El sistema calcula el porcentaje de documentos obligatorios presentes en el expediente respecto al total de documentos obligatorios configurados para ese tipo de expediente. Si el porcentaje es menor al 100%, el expediente no puede obtener estatus de aprobado. El sistema indica claramente cuáles documentos faltan.	CRITICA	Semáforo Rojo y listado de documentos faltantes.	\N	t	\N	\N	\N	t	2026-10-15 21:53:58.049805
62c8f2d1-cb82-490a-b733-b6fa1e73e3ac	RIE-01-CSF	Completitud: Constancia de Situación Fiscal	RIE	El expediente corporativo debe contener la Constancia de Situación Fiscal. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta la Constancia de Situación Fiscal.	CSF_SAT	t	CORPORATIVO	\N	\N	t	2026-10-15 21:53:58.049805
fcd7c848-1ecb-434d-95bb-26c589b29d81	RIE-01-DOM	Completitud: Comprobante de Domicilio Fiscal	RIE	El expediente corporativo debe contener el Comprobante de Domicilio Fiscal. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Comprobante de Domicilio Fiscal.	COMP_DOMICILIO	t	CORPORATIVO	\N	\N	t	2026-10-15 21:53:58.049805
3f3fb25f-6d0d-438d-8b10-35648e21163d	RIE-01-ACTA	Completitud: Acta Constitutiva	RIE	El expediente corporativo debe contener el Acta Constitutiva. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Acta Constitutiva.	ACTA_CONSTITUTIVA	t	CORPORATIVO	\N	\N	t	2026-10-15 21:53:58.049805
6e58298f-4656-4a28-abd0-834c92480ca6	RIE-01-JUR-CONT	Completitud: Contrato de Prestación de Servicios	RIE	El expediente jurídico debe contener el Contrato de Prestación de Servicios. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Contrato de Prestación de Servicios.	CONTRATO_SERVICIOS	t	JURIDICO	\N	\N	t	2026-10-15 21:53:58.049805
5b2fe7d7-52a0-4f57-84c1-9fbff9b585a5	RIE-01-JUR-NDA	Completitud: Acuerdo de Confidencialidad (NDA)	RIE	El expediente jurídico debe contener el Acuerdo de Confidencialidad (NDA). Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Acuerdo de Confidencialidad (NDA).	ACUERDO_CONFIDENCIALIDAD	t	JURIDICO	\N	\N	t	2026-10-15 21:53:58.049805
2e12f886-3ae7-42ca-bb7a-3093f95a2875	RIE-01-JUR-PODER	Completitud: Poder Notarial del representante	RIE	El expediente jurídico debe contener el Poder Notarial del representante. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Poder Notarial del representante.	PODER_NOTARIAL	t	JURIDICO	\N	\N	t	2026-10-15 21:53:58.049805
6756b61a-ab15-4d0f-b42c-77873bdfd24f	RIE-01-REG-LIC	Completitud: Licencia de Operación	RIE	El expediente regulatorio debe contener la Licencia de Operación. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta la Licencia de Operación.	LICENCIA_OPERACION	t	REGULATORIO	\N	\N	t	2026-10-15 21:53:58.049805
ceb1173d-8e36-4da7-8641-1e2e680b1fa2	RIE-01-REG-PERM	Completitud: Permiso Municipal o Sectorial	RIE	El expediente regulatorio debe contener el Permiso Municipal o Sectorial. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Permiso Municipal o Sectorial.	PERMISO_SECTORIAL	t	REGULATORIO	\N	\N	t	2026-10-15 21:53:58.049805
3bb411a0-ef1c-4963-8bfe-4dbbea6ae436	RIE-01-REG-POL	Completitud: Póliza de Seguro	RIE	El expediente regulatorio debe contener la Póliza de Seguro. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta la Póliza de Seguro.	POLIZA_SEGURO	t	REGULATORIO	\N	\N	t	2026-10-15 21:53:58.049805
77eecbfe-74e3-4090-8361-597a0bbd3e08	RIE-01-REG-REGS	Completitud: Registro ante Autoridad Sectorial	RIE	El expediente regulatorio debe contener el Registro ante Autoridad Sectorial. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Registro ante Autoridad Sectorial.	REGISTRO_SECTORIAL	t	REGULATORIO	\N	\N	t	2026-10-15 21:53:58.049805
ae2d8678-1dc3-42d3-870b-b287c44093bf	RIE-02-CONT-ANX	Anexos legales del Contrato de Prestación de Servicios	RIE	Si el expediente contiene un Contrato de Prestación de Servicios, debe incluir también sus anexos legales. La ausencia del anexo invalida el documento principal (RIE-02).	ALTA	Semáforo Rojo con indicación específica del anexo ausente.	ANEXO_CONTRATO	t	\N	CONTRATO_SERVICIOS	\N	t	2026-10-15 21:53:58.049805
ef8cef18-fad7-4ace-bad2-5d4dbe3c9575	RIE-02	Vinculación Obligatoria de Anexos	RIE	Si un documento principal (por ejemplo, un Contrato de Prestación de Servicios) requiere anexos vinculados (como una Propuesta Técnica o una Póliza de Fianza), la ausencia de cualquiera de los anexos invalida el documento principal.	ALTA	Semáforo Rojo con indicación específica del anexo ausente.	\N	t	\N	\N	\N	t	2026-10-15 21:53:58.049805
5b882533-ef27-48d9-8d5d-4cb603d1e81c	RIE-03	Integridad Criptográfica del Archivo	RIE	Al consultar un documento previamente cargado, el sistema recalcula su huella criptográfica SHA-256 y la compara con el valor registrado en la base de datos al momento de la carga inicial. Si los valores no coinciden, se ha detectado una alteración no autorizada del archivo.	CRITICA	Bloqueo inmediato del documento y registro en bitácora de auditoría.	\N	t	\N	\N	\N	t	2026-10-15 21:53:58.049805
66cb8d81-abed-4a19-8ca5-5a3e7d6eaaad	RCV-01	Vigencia Mandatoria	RCV	El sistema calcula la diferencia en días entre la fecha de vencimiento del documento y la fecha actual. Si la diferencia es negativa, el documento está vencido (Severidad Alta, Semáforo Rojo). Si está entre 0 y 30 días, el documento está próximo a vencer (Severidad Media, Semáforo Amarillo). Si es mayor a 30 días, el documento está vigente (Semáforo Verde).	ALTA	Vencido: Semáforo Rojo. Próximo a vencer (0-30 días): Semáforo Amarillo. Vigente (>30 días): Semáforo Verde.	\N	t	\N	\N	30	t	2026-10-15 21:53:58.049805
c79bd853-126c-4ed8-aefc-19844c13efdb	RCV-02	Caducidad Estricta del Comprobante de Domicilio Fiscal	RCV	El comprobante de domicilio fiscal tiene una vigencia legal predeterminada: no puede tener más de 90 días naturales de antigüedad. El sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión del documento; si supera los 90 días, el documento se marca automáticamente como vencido y requiere actualización inmediata. Si el documento no declara fecha de emisión, la antigüedad no puede verificarse y el caso se turna a revisión humana.	ALTA	Más de 90 días desde la emisión: documento vencido, Semáforo Rojo y solicitud de un comprobante actualizado.	COMP_DOMICILIO	t	\N	\N	90	t	2026-10-15 21:53:58.049805
157a2459-8fbf-45c4-beef-33e3b6e3eedb	RCV-03	Caducidad Estricta de la Constancia de Situación Fiscal	RCV	La constancia de situación fiscal debe haberse emitido en los últimos 3 meses (90 días naturales), conforme al inventario del expediente corporativo del DOC-02. El sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión; si supera los 90 días, la constancia se marca como vencida y debe solicitarse una actualizada al portal del SAT. Si el documento no declara fecha de emisión, el caso se turna a revisión humana.	ALTA	Más de 90 días desde la emisión: constancia vencida, Semáforo Rojo y solicitud de una constancia actualizada.	CSF_SAT	t	\N	\N	90	t	2026-10-15 21:53:58.049805
2816785a-84e7-422b-8b51-df2fa20fa6a9	RCV-04	Caducidad Estricta de la Opinión de Cumplimiento (32-D)	RCV	La opinión de cumplimiento de obligaciones fiscales (artículo 32-D del Código Fiscal de la Federación) tiene una vigencia de 30 días naturales a partir de su emisión (DOC-05, caducidad estricta). El sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión; si supera los 30 días, la opinión se marca como vencida. Si el documento no declara fecha de emisión, el caso se turna a revisión humana.	ALTA	Más de 30 días desde la emisión: opinión vencida, Semáforo Rojo y solicitud de una opinión actualizada al portal del SAT.	OPINION_CUMPLIMIENTO	f	\N	\N	30	t	2026-10-15 21:53:58.049805
9e678dc6-d0c8-4cb6-aaea-8573a84b0f64	RSC-OPIN-SENT	Sentido positivo de la opinión de cumplimiento	RSC	La opinión de cumplimiento declara expresamente su sentido. Positivo: el contribuyente está al corriente de sus obligaciones fiscales. Negativo: el dictamen es NO_CONFORME. Sin obligaciones, no inscrito o sin sentido legible: revisión humana.	ALTA	Solicitar al titular una opinión de cumplimiento en sentido positivo emitida en los últimos 30 días; si es negativa, debe regularizar su situación fiscal ante el SAT antes de continuar.	OPINION_CUMPLIMIENTO	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
5136c169-0409-4d10-9762-d8f70db87c60	RSC-02-CONT	Datos del firmante y representación legal	RSC	La inteligencia artificial extrae del documento los datos visibles del firmante (nombre, cargo y empresa que representa) y los presenta al analista, que confirma si corresponden con las facultades acreditadas en el poder notarial o el acta constitutiva del mismo expediente (DOC-05, RSC-02; RN-03).	ALTA	Confirmar que el firmante del titular corresponde con un apoderado con facultades vigentes en el poder notarial o el acta constitutiva del expediente y ratificar el dictamen con esa justificación (RN-03, RN-05).	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
b9721079-2aa5-4eb5-becb-f18e85d0ef2c	RSC-02-NDA	Datos del firmante y representación legal	RSC	La inteligencia artificial extrae del documento los datos visibles del firmante (nombre, cargo y empresa que representa) y los presenta al analista, que confirma si corresponden con las facultades acreditadas en el poder notarial o el acta constitutiva del mismo expediente (DOC-05, RSC-02; RN-03).	ALTA	Confirmar que el firmante del titular corresponde con un apoderado con facultades vigentes en el poder notarial o el acta constitutiva del expediente y ratificar el dictamen con esa justificación (RN-03, RN-05).	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
6a000ad2-0073-485a-95d1-dffe771affc4	RSC-01-CONT-OBJ	Objeto del contrato	RSC	El contrato define su objeto: los servicios que se prestan.	MEDIA_ALTA	Solicitar la versión del contrato que defina con claridad el objeto de los servicios.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
dd5e5441-a8e6-4a99-906c-33d296bf58f3	RSC-01-CONT-VIG	Vigencia y terminación anticipada	RSC	El contrato establece su vigencia o duración y el procedimiento de terminación anticipada o rescisión.	MEDIA_ALTA	Revisar con el área jurídica la vigencia y la cláusula de rescisión; si faltan, solicitar un convenio modificatorio que las incorpore.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
f0f6c1db-f0da-46da-841f-36d331d5b6f7	RSC-01-CONT-PEN	Penalización por incumplimiento	RSC	El contrato establece penas convencionales o penalizaciones por incumplimiento.	MEDIA_ALTA	Omisión contractual relevante: revisar con el área jurídica la inclusión de penas convencionales.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
5f7c6cb3-0294-42f9-8f07-a8ee64771650	RSC-01-CONT-CONF	Confidencialidad y no divulgación	RSC	El contrato incluye una obligación de confidencialidad o de no divulgación entre las partes.	MEDIA_ALTA	Omisión contractual relevante: incorporar la cláusula de confidencialidad o anexar un acuerdo de confidencialidad (NDA).	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
c92f3a54-6ed2-4787-a583-638328ab8eed	RSC-01-CONT-FIRM	Firmas de las partes	RSC	El contrato identifica a las partes y contiene el apartado de firmas de sus representantes.	MEDIA_ALTA	Solicitar el ejemplar firmado por todas las partes.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
f4b3f278-6765-444f-beac-4ee6a812c28c	RSC-01-NDA-NODIV	Cláusula de no divulgación	RSC	El acuerdo contiene una cláusula de no divulgación de la información confidencial.	MEDIA_ALTA	Solicitar la versión del acuerdo que incluya la obligación de no divulgación.	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
5beb846c-394e-492b-bf0b-b2807ee3eebf	RSC-01-NDA-PART	Identificación de las partes	RSC	El acuerdo identifica a las partes que se obligan a la confidencialidad.	MEDIA_ALTA	Solicitar el acuerdo con la identificación completa de las partes.	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
35cda55a-dc44-4831-8c1f-eb12aedf4c17	RSC-01-NDA-VIG	Vigencia de la confidencialidad	RSC	El acuerdo establece la vigencia o duración de la obligación de confidencialidad.	MEDIA_ALTA	Revisar con el área jurídica la vigencia de la obligación de confidencialidad.	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
65f9379d-6376-42ba-8a28-d5a5f80a5388	RSC-ACTA-ESCR	Escritura pública y notario	RSC	El acta indica el número de escritura o instrumento público y el notario o corredor público ante quien se otorgó.	MEDIA_ALTA	Solicitar la copia certificada completa del acta, en la que consten el número de escritura y los datos del notario.	ACTA_CONSTITUTIVA	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
595c3db1-92e2-4bc8-9536-4e02377aecbf	RSC-ACTA-RPC	Inscripción en el Registro Público de Comercio	RSC	El acta incluye la constancia o los datos de inscripción en el Registro Público de la Propiedad y del Comercio (folio mercantil).	MEDIA_ALTA	Solicitar la boleta o constancia de inscripción en el Registro Público de Comercio.	ACTA_CONSTITUTIVA	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
964747af-de3c-440d-8070-28269647fc8c	RSC-ACTA-ADMON	Administración y facultades de representación	RSC	El acta designa al órgano de administración (administrador único o consejo de administración) y señala quién ejerce la representación legal y con qué facultades.	MEDIA_ALTA	Verificar en el acta o en un poder notarial vigente quién ejerce la representación legal y con qué facultades (RN-03).	ACTA_CONSTITUTIVA	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
ff5e1946-5b6a-45fc-95f3-f4c76479b69a	RSC-PODER-NOT	Otorgamiento ante notario	RSC	El poder fue otorgado ante notario público e indica el número de escritura.	MEDIA_ALTA	Solicitar el testimonio notarial del poder con el número de escritura.	PODER_NOTARIAL	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
92e38667-bfbf-48d4-a969-dec4bc152ab0	RSC-PODER-PART	Otorgante y apoderado	RSC	El poder identifica al otorgante (poderdante) y al apoderado.	MEDIA_ALTA	Solicitar el poder con la identificación completa del otorgante y del apoderado.	PODER_NOTARIAL	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
1770eb42-9526-4a9e-b30b-c53bf8ab8ac0	RSC-PODER-FAC	Facultades conferidas	RSC	El poder señala las facultades conferidas: pleitos y cobranzas, actos de administración o actos de dominio.	MEDIA_ALTA	Verificar que las facultades del apoderado basten para los actos que suscribe (RN-03).	PODER_NOTARIAL	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
3e11bf03-483b-4016-bebe-65f22aa13678	RSC-POL-COB	Coberturas y suma asegurada	RSC	La póliza especifica las coberturas contratadas y la suma asegurada.	MEDIA_ALTA	Solicitar la carátula de la póliza con el detalle de coberturas y suma asegurada.	POLIZA_SEGURO	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
5107afc1-9910-4d8a-b7bc-2fbc8895c0a6	RSC-LIC-GIRO	Giro o actividad autorizada	RSC	La licencia indica el giro o la actividad que autoriza a operar.	MEDIA_ALTA	Verificar que la licencia corresponda al giro empresarial del titular; si no lo indica, solicitar la licencia completa.	LICENCIA_OPERACION	f	\N	\N	\N	t	2026-10-15 21:53:58.049805
\.


--
-- Data for Name: titulares_expediente; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.titulares_expediente (id, rfc, razon_social, tipo_persona, categoria, creado_en) FROM stdin;
b99b85e0-0040-4d3d-9f9a-a7f36f1e7d43	BIM980101XYZ	GRUPO BIMBO S.A.B. DE C.V.	MORAL	PROVEEDOR_CRITICO	2026-10-15 21:53:59.923693
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.usuarios (id, email, password_hash, nombre_completo, rol, activo, creado_en, debe_cambiar_contrasena, intentos_fallidos, bloqueado_hasta, ultimo_acceso, mfa_secreto, mfa_habilitado) FROM stdin;
0b50e554-b2c7-4be1-b371-a366ffa024ba	admin@example.com	$2b$12$FKVQ.VobcBRFqgzuZTi9..U1.BIQtHSUVlDgLW8.MgxSJ/dBFnUN6	Administración (demostración)	ADMIN	t	2026-10-15 21:54:01.81972	f	0	\N	\N	\N	f
d6f51d1b-fb16-4536-b61b-19a62858e448	validador@example.com	$2b$12$.255PsMLnFDAr6wTQyGpfed2ionHoqwA0esu2IqR6Kro.2z/5dVkW	Validación (demostración)	VALIDADOR	t	2026-10-15 21:54:02.09466	f	0	\N	\N	\N	f
ffa30ec9-b694-4cad-9f83-67c7106afb14	auditor@example.com	$2b$12$Kh4AOzJ.vnL1q8gb3dKopuI3J2OyTRyCrzeeK6Cr/0Buj.wJad.EK	Auditoría (demostración)	AUDITOR	t	2026-10-15 21:54:02.354039	f	0	\N	\N	\N	f
e8eb0290-3870-430b-b372-0f694bbca643	consulta@example.com	$2b$12$zw9G2fojlOeeSSaDGxHr6.vkCAokLn1Rmo2K5zHSc6F5dqNNHh3Vi	Consulta (demostración)	CONSULTA	t	2026-10-15 21:54:02.61477	f	0	\N	\N	\N	f
\.


--
-- Name: bitacora_auditoria bitacora_auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bitacora_auditoria
    ADD CONSTRAINT bitacora_auditoria_pkey PRIMARY KEY (id);


--
-- Name: bitacora_auditoria bitacora_auditoria_secuencia_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bitacora_auditoria
    ADD CONSTRAINT bitacora_auditoria_secuencia_key UNIQUE (secuencia);


--
-- Name: dictamenes_auditoria dictamenes_auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dictamenes_auditoria
    ADD CONSTRAINT dictamenes_auditoria_pkey PRIMARY KEY (id);


--
-- Name: documentos documentos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos
    ADD CONSTRAINT documentos_pkey PRIMARY KEY (id);


--
-- Name: expediente_asignaciones expediente_asignaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expediente_asignaciones
    ADD CONSTRAINT expediente_asignaciones_pkey PRIMARY KEY (id);


--
-- Name: expedientes expedientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expedientes
    ADD CONSTRAINT expedientes_pkey PRIMARY KEY (id);


--
-- Name: parametros_sistema parametros_sistema_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_sistema
    ADD CONSTRAINT parametros_sistema_pkey PRIMARY KEY (clave);


--
-- Name: reglas_validacion reglas_validacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reglas_validacion
    ADD CONSTRAINT reglas_validacion_pkey PRIMARY KEY (id);


--
-- Name: titulares_expediente titulares_expediente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.titulares_expediente
    ADD CONSTRAINT titulares_expediente_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: expediente_asignaciones ux_expediente_asignaciones_par; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expediente_asignaciones
    ADD CONSTRAINT ux_expediente_asignaciones_par UNIQUE (expediente_id, usuario_id);


--
-- Name: ix_bitacora_auditoria_creado_en; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bitacora_auditoria_creado_en ON public.bitacora_auditoria USING btree (creado_en);


--
-- Name: ix_bitacora_auditoria_documento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bitacora_auditoria_documento_id ON public.bitacora_auditoria USING btree (documento_id);


--
-- Name: ix_bitacora_auditoria_evento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bitacora_auditoria_evento ON public.bitacora_auditoria USING btree (evento);


--
-- Name: ix_bitacora_auditoria_expediente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bitacora_auditoria_expediente_id ON public.bitacora_auditoria USING btree (expediente_id);


--
-- Name: ix_dictamenes_auditoria_documento_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dictamenes_auditoria_documento_id ON public.dictamenes_auditoria USING btree (documento_id);


--
-- Name: ix_dictamenes_auditoria_expediente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dictamenes_auditoria_expediente_id ON public.dictamenes_auditoria USING btree (expediente_id);


--
-- Name: ix_documentos_expediente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documentos_expediente_id ON public.documentos USING btree (expediente_id);


--
-- Name: ix_documentos_hash_sha256; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documentos_hash_sha256 ON public.documentos USING btree (hash_sha256);


--
-- Name: ix_expediente_asignaciones_expediente_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expediente_asignaciones_expediente_id ON public.expediente_asignaciones USING btree (expediente_id);


--
-- Name: ix_expediente_asignaciones_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expediente_asignaciones_usuario_id ON public.expediente_asignaciones USING btree (usuario_id);


--
-- Name: ix_expedientes_codigo_expediente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_expedientes_codigo_expediente ON public.expedientes USING btree (codigo_expediente);


--
-- Name: ix_expedientes_creado_en; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expedientes_creado_en ON public.expedientes USING btree (creado_en);


--
-- Name: ix_expedientes_tipo_expediente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expedientes_tipo_expediente ON public.expedientes USING btree (tipo_expediente);


--
-- Name: ix_reglas_validacion_codigo_regla; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_reglas_validacion_codigo_regla ON public.reglas_validacion USING btree (codigo_regla);


--
-- Name: ix_titulares_expediente_rfc; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_titulares_expediente_rfc ON public.titulares_expediente USING btree (rfc);


--
-- Name: ix_usuarios_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_usuarios_email ON public.usuarios USING btree (email);


--
-- Name: ux_bitacora_secuencia; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_bitacora_secuencia ON public.bitacora_auditoria USING btree (secuencia);


--
-- Name: bitacora_auditoria trg_bitacora_inmutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bitacora_inmutable BEFORE DELETE OR UPDATE ON public.bitacora_auditoria FOR EACH ROW EXECUTE FUNCTION public.bitacora_inmutable();


--
-- Name: dictamenes_auditoria trg_dictamen_protegido; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_dictamen_protegido BEFORE DELETE OR UPDATE ON public.dictamenes_auditoria FOR EACH ROW EXECUTE FUNCTION public.dictamen_protegido();


--
-- Name: dictamenes_auditoria dictamenes_auditoria_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dictamenes_auditoria
    ADD CONSTRAINT dictamenes_auditoria_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documentos(id) ON DELETE RESTRICT;


--
-- Name: dictamenes_auditoria dictamenes_auditoria_expediente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dictamenes_auditoria
    ADD CONSTRAINT dictamenes_auditoria_expediente_id_fkey FOREIGN KEY (expediente_id) REFERENCES public.expedientes(id) ON DELETE RESTRICT;


--
-- Name: documentos documentos_expediente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos
    ADD CONSTRAINT documentos_expediente_id_fkey FOREIGN KEY (expediente_id) REFERENCES public.expedientes(id) ON DELETE RESTRICT;


--
-- Name: expediente_asignaciones expediente_asignaciones_expediente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expediente_asignaciones
    ADD CONSTRAINT expediente_asignaciones_expediente_id_fkey FOREIGN KEY (expediente_id) REFERENCES public.expedientes(id) ON DELETE RESTRICT;


--
-- Name: expediente_asignaciones expediente_asignaciones_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expediente_asignaciones
    ADD CONSTRAINT expediente_asignaciones_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: expedientes expedientes_titular_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expedientes
    ADD CONSTRAINT expedientes_titular_id_fkey FOREIGN KEY (titular_id) REFERENCES public.titulares_expediente(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--


