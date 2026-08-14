# Jonayo

Sitio personal tipo feed/blog donde presento mi software. Construido con HTML, CSS y JavaScript vanilla, sin frameworks ni backend. Publicado con GitHub Pages.

## Cómo publicar algo nuevo

No hay base de datos: los posts viven en un array `POSTS` dentro de `index.html`. Para publicar:

1. Abrí `index.html` desde el navegador de GitHub (ícono del lápiz) y buscá `const POSTS = [`.
2. Copiá un bloque `{ ... }` completo de los existentes y pegalo arriba de todos (justo debajo de `const POSTS = [`).
3. Cambiá `id` (inventate uno que no se repita), `date` (fecha de hoy), `title`, `description` y `downloadUrl`.
4. Hacé commit y esperá menos de un minuto: el sitio se actualiza solo.

> **Opcional:** para mostrar botoncitos brillosos bajo el título usá
> `badges: ["Nuevo", "GRATIS"]` (se colorean solos: los que contienen
> "nuevo" en verde/cian y los de "gratis"/"free" en naranja).

El orden es automático por fecha, así que nunca hace falta reordenar a mano: el más nuevo siempre queda arriba.

## Cómo marcar una herramienta como actualizada

1. Buscá su bloque existente en `index.html`.
2. Cambiá su `date` a la fecha de hoy.
3. Agregale `updated: true`.
4. Editá la descripción si querés contar qué cambió.

Con eso sube arriba y le aparece la etiqueta azul "actualizado".

Todos estos pasos también están comentados dentro del `<script>` del propio `index.html`.