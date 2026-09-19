// ========================================
// ALERTAS AUTOMÁTICAS
// ========================================

let alertaActualId = null;

let consultandoAlertas = false;

// ========================================
// SONIDO DE ALERTAS
// ========================================

let sonidoAlertaPreparado = false;


async function prepararSonidoAlerta() {

    if (sonidoAlertaPreparado) {
        return;
    }


    const audio =
        document.getElementById(
            "sonido-alerta"
        );


    if (!audio) {

        console.log(
            "No se encontró #sonido-alerta"
        );

        return;
    }


    try {

        const volumenOriginal =
            audio.volume;


        // Lo reproducimos en silencio
        // aprovechando la interacción
        // del usuario.

        audio.volume = 0;

        audio.currentTime = 0;

        await audio.play();


        audio.pause();

        audio.currentTime = 0;

        audio.volume =
            volumenOriginal;


        sonidoAlertaPreparado = true;


        console.log(
            "Sonido de alertas preparado."
        );

    }

    catch (error) {

        console.log(
            "No se pudo preparar el sonido:",
            error
        );

    }

}


async function reproducirSonidoAlerta() {

    const audio =
        document.getElementById(
            "sonido-alerta"
        );


    if (!audio) {

        console.log(
            "No se encontró el sonido de alerta."
        );

        return;
    }


    try {

        audio.pause();

        audio.currentTime = 0;

        audio.volume = 1;


        await audio.play();


        console.log(
            "Sonido de alerta reproducido."
        );

    }

    catch (error) {

        console.log(
            "No se pudo reproducir el sonido:",
            error
        );

    }

}


// ========================================
// DESBLOQUEAR AUDIO
// ========================================

document.addEventListener(
    "pointerdown",
    prepararSonidoAlerta,
    {
        once: true
    }
);


document.addEventListener(
    "keydown",
    prepararSonidoAlerta,
    {
        once: true
    }
);


// ========================================
// PREPARAR SONIDO
// ========================================

function prepararSonidoAlerta() {

    const audio =
        document.getElementById(
            "sonido-alerta"
        );


    if (!audio) {
        return;
    }


    audio.load();

}


// El navegador necesita que el usuario
// interactúe con la página al menos una vez.

document.addEventListener(
    "pointerdown",
    prepararSonidoAlerta,
    {
        once: true
    }
);


document.addEventListener(
    "keydown",
    prepararSonidoAlerta,
    {
        once: true
    }
);

// ========================================
// CONSULTAR ALERTAS
// ========================================

async function consultarAlertas() {

    // Si ya hay una alerta en pantalla,
    // no mostramos otra encima.

    if (
        alertaActualId !== null
        ||
        consultandoAlertas
    ) {
        return;
    }


    consultandoAlertas = true;


    try {

        const respuesta =
            await fetch(
                "/alertas/pendiente",
                {
                    method: "GET",
                    cache: "no-store"
                }
            );


        if (!respuesta.ok) {
            return;
        }


        const resultado =
            await respuesta.json();


        if (
            !resultado.ok
            ||
            !resultado.alerta
        ) {
            return;
        }


        mostrarAlerta(
            resultado.alerta
        );

    }

    catch (error) {

        console.error(
            "Error consultando alertas:",
            error
        );

    }

    finally {

        consultandoAlertas = false;

    }

}


// ========================================
// MOSTRAR ALERTA
// ========================================

function mostrarAlerta(alerta) {

    alertaActualId =
        alerta.id;


    const popup =
        document.getElementById(
            "alerta-popup"
        );


    const titulo =
        document.getElementById(
            "alerta-popup-titulo"
        );


    const mensaje =
        document.getElementById(
            "alerta-popup-mensaje"
        );


    if (
        !popup
        ||
        !titulo
        ||
        !mensaje
    ) {
        return;
    }


    // --------------------------------
    // TITULO SEGÚN TIPO
    // --------------------------------

    if (
        alerta.tipo === "TOUR_CERRADO"
    ) {

        titulo.textContent =
            "Tour cerrado";

    }

    else if (
        alerta.tipo === "FALTAN_15"
    ) {

        titulo.textContent =
            "Capacidad casi completa";

    }

    else if (
        alerta.tipo === "FALTAN_20"
    ) {

        titulo.textContent =
            "Aviso de capacidad";

    }
    else if (
        alerta.tipo === "NUEVO_PROTOCOLO"
    ) {

        titulo.textContent =
            "Nuevo protocolo";

    }

    else {

        titulo.textContent =
            "Aviso";

    }


    mensaje.textContent =
        alerta.mensaje;


    popup.hidden = false;
    reproducirSonidoAlerta();

}


// ========================================
// ENTENDIDO
// ========================================

async function marcarAlertaEntendida() {

    if (
        alertaActualId === null
    ) {
        return;
    }


    const csrf =
        document.getElementById(
            "csrf-alertas"
        );


    const datos =
        new URLSearchParams();


    datos.append(
        "csrf_token",
        csrf ? csrf.value : ""
    );


    try {

        const respuesta =
            await fetch(
                `/alertas/${alertaActualId}/entendido`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/x-www-form-urlencoded"
                    },

                    body: datos
                }
            );


        const resultado =
            await respuesta.json();


        if (!resultado.ok) {

            alert(
                resultado.error
                ||
                "No se pudo confirmar la alerta."
            );

            return;

        }


        document.getElementById(
            "alerta-popup"
        ).hidden = true;


        alertaActualId = null;


        // Si hay otra pendiente,
        // la buscamos inmediatamente.

        setTimeout(
            consultarAlertas,
            300
        );

    }

    catch (error) {

        console.error(error);

    }

}


// ========================================
// INICIAR CONSULTA AUTOMÁTICA
// ========================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        consultarAlertas();


        setInterval(
            consultarAlertas,
            4000
        );

    }
);