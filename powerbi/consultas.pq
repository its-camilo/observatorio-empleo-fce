// ============================================================================
// Observatorio de Empleo FCE — Consultas de Power Query (Power BI Desktop)
// Uso: Inicio → Transformar datos → Nueva consulta → Consulta en blanco →
//      Editor avanzado → pegue cada bloque como una consulta con el nombre indicado.
// Cambie BaseUrl por la dirección del aplicativo. Si el servidor usa CSV_TOKEN, póngalo en Token.
// ============================================================================

// ---- Consulta: Parametros (nombre: Parametros) ----
[
    BaseUrl = "https://observatorio-empleo-fce.vercel.app",
    Token = "",
    // Filtrar un semestre (vacío = histórico completo)
    Semestre = ""
]

// ---- Consulta: LeerTabla (función) ----
(tabla as text, optional incluirDescripcion as logical) as table =>
let
    P = Parametros,
    Opciones = (n as number) as record =>
        [Query = Record.Combine({
            [pagina = Text.From(n), tamano = "5000"],
            if P[Token] <> "" then [token = P[Token]] else [],
            if P[Semestre] <> "" then [semestre = P[Semestre]] else [],
            if incluirDescripcion = true then [descripcion = "true"] else []
        }), Timeout = #duration(0, 0, 2, 0)],
    // RelativePath mantiene fija la URL base: así Power BI Service puede actualizarla
    Pagina = (n as number) as table =>
        let
            Fuente = Web.Contents(P[BaseUrl], Record.Combine({[RelativePath = "api/publico/" & tabla & ".csv"], Opciones(n)})),
            Csv = Csv.Document(Fuente, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
            Tabla = Table.PromoteHeaders(Csv, [PromoteAllScalars = true])
        in Tabla,
    Paginas = List.Generate(
        () => [n = 1, t = Pagina(1)],
        each Table.RowCount([t]) > 0,
        each [n = [n] + 1, t = Pagina([n] + 1)],
        each [t]),
    Todo = if List.IsEmpty(Paginas) then Pagina(1) else Table.Combine(Paginas)
in
    Todo

// ---- Consulta: Ofertas ----
let
    Fuente = LeerTabla("ofertas"),
    Tipos = Table.TransformColumnTypes(Fuente, {
        {"fecha_publicacion", type date}, {"fecha_extraccion", type date}, {"num_softwares", Int64.Type}})
in
    Tipos

// ---- Consulta: OfertaSoftware ----
LeerTabla("oferta_software")

// ---- Consulta: OfertaCarrera (una fila por oferta y carrera; úsela para filtrar por carrera) ----
LeerTabla("oferta_carrera")

// ---- Consulta: Catalogo ----
LeerTabla("catalogo")

// ---- Consulta: Ejecuciones ----
let
    Fuente = LeerTabla("ejecuciones"),
    Tipos = Table.TransformColumnTypes(Fuente, {{"fecha", type date}, {"ofertas_encontradas", Int64.Type},
        {"duplicados_eliminados", Int64.Type}, {"ofertas_guardadas", Int64.Type}, {"total_corte", Int64.Type}})
in
    Tipos

// ---- Consulta: Cursos ----
LeerTabla("cursos")
