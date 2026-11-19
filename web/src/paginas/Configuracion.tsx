import { useCallback } from "react";
import { useEsAdmin } from "../main";
import {
  EditorJsonAvanzado,
  EditorParametro,
  ordenarParams,
  type ParamConfig,
} from "../configuracion/EditorParametro";
import { Aviso, Cargando, Titulo, useDatos } from "../componentes/ui";

type Param = ParamConfig;

export function ConfiguracionGeneral({ embebido = false }: { embebido?: boolean }) {
  const admin = useEsAdmin();
  const { datos, error, recargar } = useDatos<Param[]>("/config");
  const extras = useDatos<Param[]>(admin ? "/config/extras" : null);

  const recargarTodo = useCallback(() => {
    recargar();
    if (admin) extras.recargar();
  }, [admin, recargar, extras]);

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!datos) return <Cargando />;

  const mapa = Object.fromEntries(datos.map((p) => [p.clave, p]));
  const carreras = (mapa.carreras?.valor as string[]) || [];
  const distFuentes = (mapa.distribucion_fuentes?.valor as Record<string, number>) || {};
  const distCarreras = (mapa.distribucion_carreras?.valor as Record<string, number>) || {};

  const lista = ordenarParams(
    datos.map((p) => ({
      ...p,
      defecto: p.defecto ?? null,
    })),
  );

  return (
    <div className="space-y-3">
      {!embebido && <Titulo>Configuración</Titulo>}
      <Aviso>
        Parámetros de búsqueda y del procesamiento (fuentes, ciudades, ventana de días, límites, reglas de carrera, cursos).
        {admin
          ? " Use los formularios; las claves heredadas solo aparecen en JSON avanzado."
          : " Solo los administradores pueden editarlos."}
      </Aviso>

      {lista.map((p) => (
        <EditorParametro
          key={p.clave}
          p={p}
          admin={admin}
          alGuardar={recargarTodo}
          carreras={carreras}
          distFuentes={distFuentes}
          distCarreras={distCarreras}
        />
      ))}

      {admin && extras.datos && extras.datos.length > 0 && (
        <section className="space-y-3">
          <h2 className="titulo-seccion text-base md:text-lg">Parámetros avanzados (JSON)</h2>
          <p className="text-sm text-texto-suave">
            Claves heredadas de la base de datos sin formulario dedicado. Valide la sintaxis antes de guardar.
          </p>
          {extras.datos.map((e) => (
            <EditorJsonAvanzado
              key={e.clave}
              clave={e.clave}
              valor={e.valor}
              descripcion={e.descripcion}
              admin={admin}
              alGuardar={recargarTodo}
            />
          ))}
        </section>
      )}
    </div>
  );
}