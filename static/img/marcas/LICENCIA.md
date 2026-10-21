# Procedencia de los logos de marca

Los archivos `.svg` de esta carpeta son el glifo de marca oficial tal como
lo publica el proyecto **Simple Icons** (<https://simpleicons.org>,
<https://github.com/simple-icons/simple-icons>), obtenidos directamente de
su repositorio (`develop/icons/<nombre>.svg`) el 2026-10-22. El trazado
SVG del propio proyecto Simple Icons está bajo licencia **CC0 1.0
Universal** (dominio público) — ver su `LICENSE.md`. Las marcas en sí
(Spotify, Netflix, YouTube, Apple, Google, etc.) siguen siendo propiedad de
sus respectivos dueños; el uso aquí es puramente descriptivo, para que el
usuario identifique visualmente a qué servicio corresponde una obligación
que él mismo registró — PAYRECORD no está afiliado a ninguna de ellas.

Colores oficiales usados (verificados contra `data/simple-icons.json` del
mismo repositorio, no inventados):

| Marca | Hex |
|---|---|
| Spotify | `#1ED760` |
| Netflix | `#E50914` |
| YouTube / YouTube Music | `#FF0000` |
| Apple / Apple Music | `#000000` / `#FA243C` |
| Google | `#4285F4` |

No se encontró un icono disponible para **Disney+** ni para **Amazon
Prime** como sub-marca en Simple Icons al momento de esta implementación
(parecen haber sido retirados del proyecto). Para esas obligaciones,
PAYRECORD usa el glifo genérico de Bootstrap Icons ya incluido en el
proyecto (`bi-amazon` para Amazon/Amazon Prime) o el icono de respaldo de
la categoría (para Disney+ y cualquier otra marca no reconocida) — ver
`apps/obligaciones/services/marcas.py`.
