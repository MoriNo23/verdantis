# Handoff — change `ellipsis-body-lineas-exactas`

Estado al pausar: **8/9 tareas completas**. Falta **3.2** (mock del tablero en
Lunacy), que se quedó sin herramientas a mitad del trabajo.

## Qué ya está aplicado y commiteado en `main`

| Commit | Qué | Versión |
|---|---|---|
| `c8649b6` | `fix:` el cap del body se presupuesta con la altura REAL de la línea (`N × line_h` del propio layout) en vez de `font × 1.6` | 0.8.1 |
| (segundo commit) | `feat:` el body justificado (`set_justify(True)`) para llenar el margen sin partir palabras | 0.8.2 |

Verificado en vivo tras reiniciar el servicio: `busctl … GetServerInformation`
→ `"0.8.2"`; body de 2 líneas completo sin "..." y sin "Ver más"; body con
overflow con 3 renglones, "..." al final del tercero y la barra anclada.
Suite: 251 → 269, verde.

## Worktree del tablero (ya existe, NO lo borres)

```
/home/extra/repositorios/verdantis-diseno   (rama diseno-demos, main ya mergeado)
```

Dentro, **sin commitear** (parte de la tarea 3.1):

- `DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py`: `TABLA_DISSENY`
  refrescada con la cadena derivada (cola desde `04 etiqueta`).
- `DISEÑO-DEMOS/herramientas/manifiestos/manifiesto_esperado.json`:
  regenerado (`--self-test` exit 0).

Alturas nuevas que derivan de `src/`: `[112, 112, 108, 169, 112]` (antes
`[108, 108, 108, 148, 108]`): el body de 2 líneas pide +4 px y el de overflow
+21 px.

## Qué falta (tarea 3.2) y por qué quedó pendiente

Las 14 tools del servidor MCP `lunacy` desaparecieron del catálogo de la sesión
a mitad de la aplicación (`search({query:"lunacy"})` → vacío, sin recursos MCP,
procesos `Lunacy -mcp` muertos). Sin ellas no hay forma de editar el documento
ni de re-exportar el manifiesto real.

El usuario decidió **reiniciar la sesión** para recuperar el MCP y seguir por el
camino documentado (MCP + re-export). Al arrancar de nuevo:

1. Relanzar Lunacy con el tablero (la app está cerrada a propósito; la API solo
   hace bind al arrancar, sin retry — ver
   `../verdantis-diseno/.opencode/skills/lunacy-automation/SKILL.md`):

   ```bash
   TABLERO=/home/extra/repositorios/verdantis-diseno/DISEÑO-DEMOS/tablero-verdantis.free
   ss -ltn | grep -q 31415 || setsid nohup /opt/icons8/lunacy/Lunacy "$TABLERO" >/dev/null 2>&1 &
   for i in $(seq 1 25); do ss -ltn | grep -q 31415 && break; sleep 1; done
   ```

   Smoke test: `get_viewport_info` tiene que devolver el viewport.

2. Correr `--comparar` para tener la lista de 26 fallos y editar capa por capa:

   ```bash
   cd /home/extra/repositorios/verdantis-diseno
   python3 DISEÑO-DEMOS/herramientas/validar_geometria_tablero.py \
       --comparar DISEÑO-DEMOS/herramientas/manifiestos/manifiesto_real.json \
                  DISEÑO-DEMOS/herramientas/manifiestos/manifiesto_esperado.json
   ```

   Lo que hay que mover en el documento:

   - `size` de los grupos `01 · Toast estándar`, `02 · Toast con imagen
     izquierda`, `05 · Persistente + franja`, `06a/b/c · Wipe` → 112
     (estaban en 108), y `04 · Body largo + Ver más` → 169 (estaba 148).
   - Los hijos `fondo card 360x108` → renombrar a `360x112` (y `360x148` →
     `360x169`). Ojo: el radio del rect redondeado NO está en `cornerRadius`,
     está en `points[i][3]` por vértice (quirk de la skill).
   - `04 · Body largo + Ver más`: la barra "Ver más" baja 21 px (el body pasa de
     2 renglones mockeados a 3) y el mock del body muestra la 3ª línea.
   - Las 19 posiciones de la cola desde `04 etiqueta` (+4 px en la cabeza,
     +25 px a partir de `06 etiqueta`, +29 px desde `07 etiqueta`), tal cual
     las imprime el `--self-test`.
   - La nota `nota estado barra expandido`: valor 169.

   Quirk importante: `update_layers` NO aplica a hijos de grupos con
   `expand: true` (los mocks 01-06c) aunque devuelva éxito — hay que releer el
   grupo, mutar `layers[...]` y mandar el grupo entero con su árbol. Un id por
   payload (duplicar un id da `Arg_NullReferenceException`).

3. Re-exportar `manifiesto_real.json` desde la lectura MCP viva y correr
   `--comparar` → exit 0.

4. Commit `chore:` en `diseno-demos` y recién entonces
   `git worktree remove ../verdantis-diseno` (la rama queda; no la borres).
