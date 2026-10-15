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
1ba1535d-c9a0-4130-996e-324afe8ccf54	SELLO_GENESIS	\N	\N	\N	SISTEMA	\N	{"eventos_previos": 0, "huella_historial_previo": "0000000000000000000000000000000000000000000000000000000000000000", "desde": null, "hasta": null, "algoritmo": "SHA-256 del JSON can\\u00f3nico (claves ordenadas, UTF-8, sin espacios)"}	2026-10-15 20:27:29.783133	1	0000000000000000000000000000000000000000000000000000000000000000	271b36c784d06bcef24022c49d1cda920dd388049dccf551c55c825e9f829fed
b1c68bbc-6978-4c0f-83df-e7d4d09249b1	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "4ee985ca-dd47-43b8-8e13-88d4979d5a6b", "email": "admin@example.com", "nombre_completo": "Administraci\\u00f3n (demostraci\\u00f3n)", "rol": "ADMIN", "origen": "DEMOSTRACION"}	2026-10-15 20:27:29.792993	2	271b36c784d06bcef24022c49d1cda920dd388049dccf551c55c825e9f829fed	4f1b9d84a371da91652fa9325d4929fce1c7b9d0ad90f5a4cce31364142ece5a
e33acafc-fa6a-4ee3-aee5-6fded71986d1	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "1f990e76-994d-4b44-acc9-95ed12719706", "email": "validador@example.com", "nombre_completo": "Validaci\\u00f3n (demostraci\\u00f3n)", "rol": "VALIDADOR", "origen": "DEMOSTRACION"}	2026-10-15 20:27:30.239815	3	4f1b9d84a371da91652fa9325d4929fce1c7b9d0ad90f5a4cce31364142ece5a	8fef5e72e4c2a4b9826d28ca4efa1102f92d4aeb1f6a1ebb81b91bc87be1544d
3c035e12-54d3-4c52-8771-3e10947ede06	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "6152fd0a-c187-48de-8f00-e271371d58c0", "email": "auditor@example.com", "nombre_completo": "Auditor\\u00eda (demostraci\\u00f3n)", "rol": "AUDITOR", "origen": "DEMOSTRACION"}	2026-10-15 20:27:30.677879	4	8fef5e72e4c2a4b9826d28ca4efa1102f92d4aeb1f6a1ebb81b91bc87be1544d	c41ac488daa52800d7b186f4389e294ee0730d4bf8c6259e86dee499fadc471c
227f71af-61ba-43d6-8b6b-783f2e36313b	ALTA_USUARIO	\N	\N	\N	SISTEMA	\N	{"usuario_id": "73e4a29f-cbd3-415c-a20d-0ab5d76a503a", "email": "consulta@example.com", "nombre_completo": "Consulta (demostraci\\u00f3n)", "rol": "CONSULTA", "origen": "DEMOSTRACION"}	2026-10-15 20:27:31.122433	5	c41ac488daa52800d7b186f4389e294ee0730d4bf8c6259e86dee499fadc471c	496820d198b2b5aaa8f9fd733b35e65cc97df21e854e90ebd9542482414fae0d
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
f70e4f22-809d-4a4d-a3e0-08ef6184f776	d82a1aca-0ecf-4903-a081-d76156bdae93	EXP-BIM980101XYZ-001	CORPORATIVO	\N	EN_REVISION	0.00	2026-10-15 20:27:25.579552	2026-10-15 20:27:25.579552
\.


--
-- Data for Name: reglas_validacion; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.reglas_validacion (id, codigo_regla, nombre_regla, familia_regla, descripcion, severidad, accion, tipo_documento, documento_obligatorio, tipo_expediente, documento_principal, dias_maximos_vigencia, activo, creado_en) FROM stdin;
89d5aacd-9d3a-4efc-be99-453852365fd3	RIE-01	Completitud de Expediente	RIE	El sistema calcula el porcentaje de documentos obligatorios presentes en el expediente respecto al total de documentos obligatorios configurados para ese tipo de expediente. Si el porcentaje es menor al 100%, el expediente no puede obtener estatus de aprobado. El sistema indica claramente cuáles documentos faltan.	CRITICA	Semáforo Rojo y listado de documentos faltantes.	\N	t	\N	\N	\N	t	2026-10-15 20:27:21.56908
c09fb17e-804d-42e0-ae13-514ff8f629ed	RIE-01-CSF	Completitud: Constancia de Situación Fiscal	RIE	El expediente corporativo debe contener la Constancia de Situación Fiscal. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta la Constancia de Situación Fiscal.	CSF_SAT	t	CORPORATIVO	\N	\N	t	2026-10-15 20:27:21.56908
a32119da-f19c-4b0c-b8a7-b2f41358e5a9	RIE-01-DOM	Completitud: Comprobante de Domicilio Fiscal	RIE	El expediente corporativo debe contener el Comprobante de Domicilio Fiscal. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Comprobante de Domicilio Fiscal.	COMP_DOMICILIO	t	CORPORATIVO	\N	\N	t	2026-10-15 20:27:21.56908
34d5ab60-069c-487f-862f-bea3598422e3	RIE-01-ACTA	Completitud: Acta Constitutiva	RIE	El expediente corporativo debe contener el Acta Constitutiva. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Acta Constitutiva.	ACTA_CONSTITUTIVA	t	CORPORATIVO	\N	\N	t	2026-10-15 20:27:21.56908
4112c6c0-9f3f-4f74-a5aa-f7b7b0564ca2	RIE-01-JUR-CONT	Completitud: Contrato de Prestación de Servicios	RIE	El expediente jurídico debe contener el Contrato de Prestación de Servicios. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Contrato de Prestación de Servicios.	CONTRATO_SERVICIOS	t	JURIDICO	\N	\N	t	2026-10-15 20:27:21.56908
310b92e6-b54e-4d7e-baa1-750657996830	RIE-01-JUR-NDA	Completitud: Acuerdo de Confidencialidad (NDA)	RIE	El expediente jurídico debe contener el Acuerdo de Confidencialidad (NDA). Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Acuerdo de Confidencialidad (NDA).	ACUERDO_CONFIDENCIALIDAD	t	JURIDICO	\N	\N	t	2026-10-15 20:27:21.56908
99b922a9-44b6-40d2-b082-454fee3cc5e8	RIE-01-JUR-PODER	Completitud: Poder Notarial del representante	RIE	El expediente jurídico debe contener el Poder Notarial del representante. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Poder Notarial del representante.	PODER_NOTARIAL	t	JURIDICO	\N	\N	t	2026-10-15 20:27:21.56908
5795eef9-bc64-4368-a94b-1e07d9f530a8	RIE-01-REG-LIC	Completitud: Licencia de Operación	RIE	El expediente regulatorio debe contener la Licencia de Operación. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta la Licencia de Operación.	LICENCIA_OPERACION	t	REGULATORIO	\N	\N	t	2026-10-15 20:27:21.56908
18edd9bc-33f5-42b3-b922-d87cdcca3615	RIE-01-REG-PERM	Completitud: Permiso Municipal o Sectorial	RIE	El expediente regulatorio debe contener el Permiso Municipal o Sectorial. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Permiso Municipal o Sectorial.	PERMISO_SECTORIAL	t	REGULATORIO	\N	\N	t	2026-10-15 20:27:21.56908
4eb863cc-8a6b-488f-ab0d-b1dbd52b07ff	RIE-01-REG-POL	Completitud: Póliza de Seguro	RIE	El expediente regulatorio debe contener la Póliza de Seguro. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta la Póliza de Seguro.	POLIZA_SEGURO	t	REGULATORIO	\N	\N	t	2026-10-15 20:27:21.56908
0f945d2e-8d8f-4ab2-8aa6-5178ee40740d	RIE-01-REG-REGS	Completitud: Registro ante Autoridad Sectorial	RIE	El expediente regulatorio debe contener el Registro ante Autoridad Sectorial. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).	CRITICA	Semáforo Rojo: falta el Registro ante Autoridad Sectorial.	REGISTRO_SECTORIAL	t	REGULATORIO	\N	\N	t	2026-10-15 20:27:21.56908
44b9310f-ac30-400e-84cd-947e1e1e5706	RIE-02-CONT-ANX	Anexos legales del Contrato de Prestación de Servicios	RIE	Si el expediente contiene un Contrato de Prestación de Servicios, debe incluir también sus anexos legales. La ausencia del anexo invalida el documento principal (RIE-02).	ALTA	Semáforo Rojo con indicación específica del anexo ausente.	ANEXO_CONTRATO	t	\N	CONTRATO_SERVICIOS	\N	t	2026-10-15 20:27:21.56908
db0bb516-f640-4953-8cd5-71c89846f0fe	RIE-02	Vinculación Obligatoria de Anexos	RIE	Si un documento principal (por ejemplo, un Contrato de Prestación de Servicios) requiere anexos vinculados (como una Propuesta Técnica o una Póliza de Fianza), la ausencia de cualquiera de los anexos invalida el documento principal.	ALTA	Semáforo Rojo con indicación específica del anexo ausente.	\N	t	\N	\N	\N	t	2026-10-15 20:27:21.56908
5cbbb64e-b7de-47bc-9655-9eef5f59036f	RIE-03	Integridad Criptográfica del Archivo	RIE	Al consultar un documento previamente cargado, el sistema recalcula su huella criptográfica SHA-256 y la compara con el valor registrado en la base de datos al momento de la carga inicial. Si los valores no coinciden, se ha detectado una alteración no autorizada del archivo.	CRITICA	Bloqueo inmediato del documento y registro en bitácora de auditoría.	\N	t	\N	\N	\N	t	2026-10-15 20:27:21.56908
6ccd7065-76ee-48ab-9d5f-2083c839ee01	RCV-01	Vigencia Mandatoria	RCV	El sistema calcula la diferencia en días entre la fecha de vencimiento del documento y la fecha actual. Si la diferencia es negativa, el documento está vencido (Severidad Alta, Semáforo Rojo). Si está entre 0 y 30 días, el documento está próximo a vencer (Severidad Media, Semáforo Amarillo). Si es mayor a 30 días, el documento está vigente (Semáforo Verde).	ALTA	Vencido: Semáforo Rojo. Próximo a vencer (0-30 días): Semáforo Amarillo. Vigente (>30 días): Semáforo Verde.	\N	t	\N	\N	30	t	2026-10-15 20:27:21.56908
48b2d3b6-540d-4117-91b5-96da68716316	RCV-02	Caducidad Estricta del Comprobante de Domicilio Fiscal	RCV	El comprobante de domicilio fiscal tiene una vigencia legal predeterminada: no puede tener más de 90 días naturales de antigüedad. El sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión del documento; si supera los 90 días, el documento se marca automáticamente como vencido y requiere actualización inmediata. Si el documento no declara fecha de emisión, la antigüedad no puede verificarse y el caso se turna a revisión humana.	ALTA	Más de 90 días desde la emisión: documento vencido, Semáforo Rojo y solicitud de un comprobante actualizado.	COMP_DOMICILIO	t	\N	\N	90	t	2026-10-15 20:27:21.56908
2c22f08b-6db5-4006-857a-88377a601d70	RCV-03	Caducidad Estricta de la Constancia de Situación Fiscal	RCV	La constancia de situación fiscal debe haberse emitido en los últimos 3 meses (90 días naturales), conforme al inventario del expediente corporativo del DOC-02. El sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión; si supera los 90 días, la constancia se marca como vencida y debe solicitarse una actualizada al portal del SAT. Si el documento no declara fecha de emisión, el caso se turna a revisión humana.	ALTA	Más de 90 días desde la emisión: constancia vencida, Semáforo Rojo y solicitud de una constancia actualizada.	CSF_SAT	t	\N	\N	90	t	2026-10-15 20:27:21.56908
aaa099a6-df90-4342-8e2d-45b6a6eea010	RCV-04	Caducidad Estricta de la Opinión de Cumplimiento (32-D)	RCV	La opinión de cumplimiento de obligaciones fiscales (artículo 32-D del Código Fiscal de la Federación) tiene una vigencia de 30 días naturales a partir de su emisión (DOC-05, caducidad estricta). El sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión; si supera los 30 días, la opinión se marca como vencida. Si el documento no declara fecha de emisión, el caso se turna a revisión humana.	ALTA	Más de 30 días desde la emisión: opinión vencida, Semáforo Rojo y solicitud de una opinión actualizada al portal del SAT.	OPINION_CUMPLIMIENTO	f	\N	\N	30	t	2026-10-15 20:27:21.56908
6c8a240a-de4c-495d-8347-40d8d1d022c5	RSC-OPIN-SENT	Sentido positivo de la opinión de cumplimiento	RSC	La opinión de cumplimiento declara expresamente su sentido. Positivo: el contribuyente está al corriente de sus obligaciones fiscales. Negativo: el dictamen es NO_CONFORME. Sin obligaciones, no inscrito o sin sentido legible: revisión humana.	ALTA	Solicitar al titular una opinión de cumplimiento en sentido positivo emitida en los últimos 30 días; si es negativa, debe regularizar su situación fiscal ante el SAT antes de continuar.	OPINION_CUMPLIMIENTO	f	\N	\N	\N	t	2026-10-15 20:27:21.56908
112467e8-46e7-415e-97d8-8c3ec7ffac88	RSC-02-CONT	Datos del firmante y representación legal	RSC	La inteligencia artificial extrae del documento los datos visibles del firmante (nombre, cargo y empresa que representa) y los presenta al analista, que confirma si corresponden con las facultades acreditadas en el poder notarial o el acta constitutiva del mismo expediente (DOC-05, RSC-02; RN-03).	ALTA	Confirmar que el firmante del titular corresponde con un apoderado con facultades vigentes en el poder notarial o el acta constitutiva del expediente y ratificar el dictamen con esa justificación (RN-03, RN-05).	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 20:27:21.56908
0f981e6c-8a3a-4ce3-906e-9daa079903db	RSC-02-NDA	Datos del firmante y representación legal	RSC	La inteligencia artificial extrae del documento los datos visibles del firmante (nombre, cargo y empresa que representa) y los presenta al analista, que confirma si corresponden con las facultades acreditadas en el poder notarial o el acta constitutiva del mismo expediente (DOC-05, RSC-02; RN-03).	ALTA	Confirmar que el firmante del titular corresponde con un apoderado con facultades vigentes en el poder notarial o el acta constitutiva del expediente y ratificar el dictamen con esa justificación (RN-03, RN-05).	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 20:27:21.56908
aa2a1d30-859f-4acb-8607-4ac96ca32274	RSC-01-CONT-OBJ	Objeto del contrato	RSC	El contrato define su objeto: los servicios que se prestan.	MEDIA_ALTA	Solicitar la versión del contrato que defina con claridad el objeto de los servicios.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
544a2212-38b4-44de-9488-6d1489eaf60c	RSC-01-CONT-VIG	Vigencia y terminación anticipada	RSC	El contrato establece su vigencia o duración y el procedimiento de terminación anticipada o rescisión.	MEDIA_ALTA	Revisar con el área jurídica la vigencia y la cláusula de rescisión; si faltan, solicitar un convenio modificatorio que las incorpore.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
2ff8d108-0e72-4ca1-9137-a4d67363f780	RSC-01-CONT-PEN	Penalización por incumplimiento	RSC	El contrato establece penas convencionales o penalizaciones por incumplimiento.	MEDIA_ALTA	Omisión contractual relevante: revisar con el área jurídica la inclusión de penas convencionales.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
ffc7a26c-f7b2-402f-8100-5128640c30de	RSC-01-CONT-CONF	Confidencialidad y no divulgación	RSC	El contrato incluye una obligación de confidencialidad o de no divulgación entre las partes.	MEDIA_ALTA	Omisión contractual relevante: incorporar la cláusula de confidencialidad o anexar un acuerdo de confidencialidad (NDA).	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
e4e71946-d3b6-4a7e-bd49-9b7f3abaa3be	RSC-01-CONT-FIRM	Firmas de las partes	RSC	El contrato identifica a las partes y contiene el apartado de firmas de sus representantes.	MEDIA_ALTA	Solicitar el ejemplar firmado por todas las partes.	CONTRATO_SERVICIOS	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
4dbd191b-b093-4566-87ec-6ce5211012e4	RSC-01-NDA-NODIV	Cláusula de no divulgación	RSC	El acuerdo contiene una cláusula de no divulgación de la información confidencial.	MEDIA_ALTA	Solicitar la versión del acuerdo que incluya la obligación de no divulgación.	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
8685d1ac-8345-4d09-9b48-6c25b28c550c	RSC-01-NDA-PART	Identificación de las partes	RSC	El acuerdo identifica a las partes que se obligan a la confidencialidad.	MEDIA_ALTA	Solicitar el acuerdo con la identificación completa de las partes.	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
96307ad6-6767-4f19-8861-52571ecc955f	RSC-01-NDA-VIG	Vigencia de la confidencialidad	RSC	El acuerdo establece la vigencia o duración de la obligación de confidencialidad.	MEDIA_ALTA	Revisar con el área jurídica la vigencia de la obligación de confidencialidad.	ACUERDO_CONFIDENCIALIDAD	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
4f5a3e84-da85-4dd5-9dbe-84de3a40e204	RSC-ACTA-ESCR	Escritura pública y notario	RSC	El acta indica el número de escritura o instrumento público y el notario o corredor público ante quien se otorgó.	MEDIA_ALTA	Solicitar la copia certificada completa del acta, en la que consten el número de escritura y los datos del notario.	ACTA_CONSTITUTIVA	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
4ff83721-b4a3-484b-a107-8345e0e211ff	RSC-ACTA-RPC	Inscripción en el Registro Público de Comercio	RSC	El acta incluye la constancia o los datos de inscripción en el Registro Público de la Propiedad y del Comercio (folio mercantil).	MEDIA_ALTA	Solicitar la boleta o constancia de inscripción en el Registro Público de Comercio.	ACTA_CONSTITUTIVA	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
d0d3a2e1-fcb1-403a-a8b1-088d9e0b5f36	RSC-ACTA-ADMON	Administración y facultades de representación	RSC	El acta designa al órgano de administración (administrador único o consejo de administración) y señala quién ejerce la representación legal y con qué facultades.	MEDIA_ALTA	Verificar en el acta o en un poder notarial vigente quién ejerce la representación legal y con qué facultades (RN-03).	ACTA_CONSTITUTIVA	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
1179aec1-6dd5-420d-870b-eaff7cf936a1	RSC-PODER-NOT	Otorgamiento ante notario	RSC	El poder fue otorgado ante notario público e indica el número de escritura.	MEDIA_ALTA	Solicitar el testimonio notarial del poder con el número de escritura.	PODER_NOTARIAL	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
1fa115a9-e7e0-454d-9092-22ddc2233e68	RSC-PODER-PART	Otorgante y apoderado	RSC	El poder identifica al otorgante (poderdante) y al apoderado.	MEDIA_ALTA	Solicitar el poder con la identificación completa del otorgante y del apoderado.	PODER_NOTARIAL	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
079d5292-65dd-49f8-a503-e105e4093212	RSC-PODER-FAC	Facultades conferidas	RSC	El poder señala las facultades conferidas: pleitos y cobranzas, actos de administración o actos de dominio.	MEDIA_ALTA	Verificar que las facultades del apoderado basten para los actos que suscribe (RN-03).	PODER_NOTARIAL	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
708a2381-321d-4326-975a-03991d76f560	RSC-POL-COB	Coberturas y suma asegurada	RSC	La póliza especifica las coberturas contratadas y la suma asegurada.	MEDIA_ALTA	Solicitar la carátula de la póliza con el detalle de coberturas y suma asegurada.	POLIZA_SEGURO	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
43a1bc20-da01-4dda-9c6f-7f1d66ab3f9e	RSC-LIC-GIRO	Giro o actividad autorizada	RSC	La licencia indica el giro o la actividad que autoriza a operar.	MEDIA_ALTA	Verificar que la licencia corresponda al giro empresarial del titular; si no lo indica, solicitar la licencia completa.	LICENCIA_OPERACION	f	\N	\N	\N	t	2026-10-15 20:27:21.570075
\.


--
-- Data for Name: titulares_expediente; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.titulares_expediente (id, rfc, razon_social, tipo_persona, categoria, creado_en) FROM stdin;
d82a1aca-0ecf-4903-a081-d76156bdae93	BIM980101XYZ	GRUPO BIMBO S.A.B. DE C.V.	MORAL	PROVEEDOR_CRITICO	2026-10-15 20:27:25.573449
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.usuarios (id, email, password_hash, nombre_completo, rol, activo, creado_en, debe_cambiar_contrasena, intentos_fallidos, bloqueado_hasta, ultimo_acceso, mfa_secreto, mfa_habilitado) FROM stdin;
4ee985ca-dd47-43b8-8e13-88d4979d5a6b	admin@example.com	$2b$12$AIvWOJPrLjM.5vUeOrwu.uw8f4h8pi52I5sxCgMI8/9.okhzvOTci	Administración (demostración)	ADMIN	t	2026-10-15 20:27:29.742799	f	0	\N	\N	\N	f
1f990e76-994d-4b44-acc9-95ed12719706	validador@example.com	$2b$12$wYSwZ6Ni8A0SN3FsFiuEN.b18.wVE68oZkemHQ6.2C6wpUO8ymVNy	Validación (demostración)	VALIDADOR	t	2026-10-15 20:27:30.233136	f	0	\N	\N	\N	f
6152fd0a-c187-48de-8f00-e271371d58c0	auditor@example.com	$2b$12$jUrm0WIrdbxs1PGFnhAuq.1PZgP3qdyAgnJuyg7Alz11ZXWYE8Xsq	Auditoría (demostración)	AUDITOR	t	2026-10-15 20:27:30.667828	f	0	\N	\N	\N	f
73e4a29f-cbd3-415c-a20d-0ab5d76a503a	consulta@example.com	$2b$12$0MZCtiWlUGRoFcIbO.NYcOzclHfaLap3sEgQGyNv2DA4OiX536vy.	Consulta (demostración)	CONSULTA	t	2026-10-15 20:27:31.115079	f	0	\N	\N	\N	f
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


