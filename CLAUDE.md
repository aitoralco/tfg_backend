# Proyecto: [Backend Whaler]
## Backend: FastAPI
- Tienes que terminar este backend, mira todo lo que hay y escribe en un archivo en la raíz del proyecto los endpoints que ya existen y funcionan.
- Separa los endpoints en los que funcionan y no hay que tocar, los que hay que matizar y los que no van o no se usan.
- El backend estará arrancado en modo develop, lo que significa que cada vez que modifiques algo este se reiniciará con los canvios para que puedas probarlo.
- La dirección del backend es http://127.0.0.1:8000

## Funcionalidades que deber tener:
- Registro, Logueo y dada de baja de usuarios
- Todos los usuarios registrados tienen que ser User
- Hay que mirar que al modificar un usuario haya dos formas de hacerlo:
    1. Un usuario modifica sus datos (sin alterar su ID) y con seguridad pidiendo la contraseña de este. (el canvio de contraseña tiene que ser mas seguro)
    2. Un usuario Admin modifica los datos de otro usuario, los admins tienen permiso para modificar lo que sea de otros usuarios (excepto IDs por consistencia de la BD), incluso de otros admins.
- Los usuarios admins también pueden eliminar usuarios.
- Un usuario normal puede eliminar su cuenta (con pidiendo la contraseña)
- Un usuario tiene que poder subir videos directamente al MinIO (revisa el endpoint que lo hace, este los sube en stream directamente al MinIO sin guardar nada en el backend).
- Un usuario tiene que poder modificar lo que sea de sus videos o incluso eliminarlos.
- Cualquier usuario tiene que poder ver videos, aunque no esté registrado en la web, por lo que hace falta un endpoint que recoja un numero X de videos y envie al frontend sus "miniaturas" o una imagen de un fragmento del video para mostrar varios y que el usuario elija cual quiere ver.
- Cualquier usuario tiene que poder buscar videos por nombre, fecha de subida, descripción o incluso nombre del usuario que lo subió.
- Cuando se ve un video no se puede mandar el video completo, tiene que haber alguna forma de mandar solo los frames según se necesita para poder reproducirlo a medida que se descarga (como youtube).
- Los resultados de buscar videos o de mostrar los videos en la página inicial tienen que pensarse para estar páginados, no quiero que se devuelva toda la lista de videos de una.
- Solo tienes que modificar el backend en lo que haga falta, tienes toda la estructura de la BD en los modelos del backend, la conexión a esta funciona perfectamente, como la conexión al Redis y al MinIO.
- Dejaré la BD, MinIO y Redis encendidos, junto con el worker, para que puedas probar cualquier endpoint sin problemas si es que alguno interactua con alguno de estos servicios.