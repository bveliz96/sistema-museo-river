// ========================================
// ESTADO DEL TECLADO
// ========================================

let etapaTeclado = "HORARIO";

let horarioIngresado = "";

let capacidadIngresada = "100";

let capacidadEditada = false;

let circuitoSeleccionado = "";


// ========================================
// ESTADO DE LOS CONTADORES
// ========================================

const cantidades = {};

const guardandoIngreso = {};


// ========================================
// CSRF
// ========================================

function obtenerCsrfToken() {

    const input = document.querySelector(
        'input[name="csrf_token"]'
    );


    if (!input) {
        return "";
    }


    return input.value;

}


// ========================================
// ABRIR TECLADO
// ========================================

function abrirTeclado(circuito) {

    circuitoSeleccionado = circuito;

    etapaTeclado = "HORARIO";

    horarioIngresado = "";

    capacidadIngresada = "100";

    capacidadEditada = false;


    document.getElementById(
        "teclado-circuito"
    ).textContent =
        `${circuito} · HORARIO`;


    actualizarDisplay();


    document.getElementById(
        "modal-horario"
    ).classList.add(
        "activo"
    );

}


// ========================================
// CERRAR TECLADO
// ========================================

function cerrarTeclado() {

    document.getElementById(
        "modal-horario"
    ).classList.remove(
        "activo"
    );


    etapaTeclado = "HORARIO";

    horarioIngresado = "";

    capacidadIngresada = "100";

    capacidadEditada = false;

    circuitoSeleccionado = "";

}


// ========================================
// AGREGAR NÚMERO
// ========================================

function agregarNumero(numero) {

    // --------------------------------
    // HORARIO
    // --------------------------------

    if (
        etapaTeclado === "HORARIO"
    ) {

        if (
            horarioIngresado.length >= 4
        ) {
            return;
        }


        horarioIngresado += numero;

    }


    // --------------------------------
    // CAPACIDAD
    // --------------------------------

    else if (
        etapaTeclado === "CAPACIDAD"
    ) {

        /*
            Al entrar a capacidad aparece 100.

            Si el usuario empieza a escribir,
            reemplazamos ese 100 directamente.
        */

        if (!capacidadEditada) {

            capacidadIngresada = numero;

            capacidadEditada = true;

        }

        else {

            if (
                capacidadIngresada.length >= 4
            ) {
                return;
            }


            capacidadIngresada += numero;

        }

    }


    actualizarDisplay();

}


// ========================================
// BORRAR NÚMERO
// ========================================

function borrarNumero() {

    // --------------------------------
    // HORARIO
    // --------------------------------

    if (
        etapaTeclado === "HORARIO"
    ) {

        horarioIngresado =
            horarioIngresado.slice(
                0,
                -1
            );

    }


    // --------------------------------
    // CAPACIDAD
    // --------------------------------

    else if (
        etapaTeclado === "CAPACIDAD"
    ) {

        /*
            Si todavía estaba el 100 por defecto,
            el primer borrar lo limpia entero.
        */

        if (!capacidadEditada) {

            capacidadIngresada = "";

            capacidadEditada = true;

        }

        else {

            capacidadIngresada =
                capacidadIngresada.slice(
                    0,
                    -1
                );

        }

    }


    actualizarDisplay();

}


// ========================================
// ACTUALIZAR DISPLAY
// ========================================

function actualizarDisplay() {

    const display =
        document.getElementById(
            "horario-display"
        );


    if (!display) {
        return;
    }


    // ====================================
    // DISPLAY HORARIO
    // ====================================

    if (
        etapaTeclado === "HORARIO"
    ) {

        if (
            horarioIngresado.length === 0
        ) {

            display.textContent =
                "--:--";

            return;

        }


        if (
            horarioIngresado.length === 1
        ) {

            display.textContent =
                horarioIngresado;

            return;

        }


        if (
            horarioIngresado.length === 2
        ) {

            display.textContent =
                horarioIngresado + ":";

            return;

        }


        display.textContent =
            horarioIngresado.slice(
                0,
                2
            )
            +
            ":"
            +
            horarioIngresado.slice(
                2
            );


        return;

    }


    // ====================================
    // DISPLAY CAPACIDAD
    // ====================================

    if (
        etapaTeclado === "CAPACIDAD"
    ) {

        if (!capacidadIngresada) {

            display.textContent = "0";

        }

        else {

            display.textContent =
                capacidadIngresada;

        }

    }

}


// ========================================
// CONFIRMAR TECLADO
// ========================================

function confirmarHorario() {

    // ====================================
    // PRIMER PASO: HORARIO
    // ====================================

    if (
        etapaTeclado === "HORARIO"
    ) {

        if (
            horarioIngresado.length !== 4
        ) {

            alert(
                "Ingresá el horario completo."
            );

            return;

        }


        const horas =
            parseInt(
                horarioIngresado.slice(
                    0,
                    2
                )
            );


        const minutos =
            parseInt(
                horarioIngresado.slice(
                    2
                )
            );


        if (
            horas > 23
            ||
            minutos > 59
        ) {

            alert(
                "El horario ingresado no es válido."
            );

            return;

        }


        // --------------------------------
        // PASAR A CAPACIDAD
        // --------------------------------

        etapaTeclado = "CAPACIDAD";

        capacidadIngresada = "100";

        capacidadEditada = false;


        const horaFormateada =
            horarioIngresado.slice(
                0,
                2
            )
            +
            ":"
            +
            horarioIngresado.slice(
                2
            );


        document.getElementById(
            "teclado-circuito"
        ).textContent =
            `${circuitoSeleccionado} ${horaFormateada} · CAPACIDAD`;


        actualizarDisplay();


        return;

    }


    // ====================================
    // SEGUNDO PASO: CAPACIDAD
    // ====================================

    if (
        etapaTeclado === "CAPACIDAD"
    ) {

        const capacidad =
            parseInt(
                capacidadIngresada
            );


        if (
            isNaN(capacidad)
            ||
            capacidad <= 0
        ) {

            alert(
                "Ingresá una capacidad válida."
            );

            return;

        }


        // --------------------------------
        // COMPLETAR FORMULARIO
        // --------------------------------

        document.getElementById(
            "tour-circuito"
        ).value =
            circuitoSeleccionado;


        document.getElementById(
            "tour-hora"
        ).value =
            horarioIngresado;


        document.getElementById(
            "tour-capacidad"
        ).value =
            capacidad;


        // --------------------------------
        // ENVIAR
        // --------------------------------

        document.getElementById(
            "form-abrir-tour"
        ).submit();

    }

}


// ========================================
// CONTADOR DE PERSONAS
// ========================================

function cambiarCantidadDesdeBoton(
    boton,
    cambio
) {

    const tourId =
        boton.dataset.tourId;


    if (
        cantidades[tourId] === undefined
    ) {

        cantidades[tourId] = 1;

    }


    let nuevaCantidad =
        cantidades[tourId]
        + cambio;


    if (
        nuevaCantidad < 1
    ) {

        nuevaCantidad = 1;

    }


    cantidades[tourId] =
        nuevaCantidad;


    document.getElementById(
        `cantidad-${tourId}`
    ).textContent =
        nuevaCantidad;

}


// ========================================
// GUARDAR INGRESO
// ========================================

function guardarIngresoDesdeBoton(
    boton
) {

    const tourId =
        boton.dataset.tourId;


    const tipoVisitaId =
        boton.dataset.tipoVisitaId;


    guardarIngreso(
        tourId,
        tipoVisitaId
    );

}


async function guardarIngreso(
    tourId,
    tipoVisitaId
) {

    if (
        guardandoIngreso[tourId]
    ) {
        return;
    }


    guardandoIngreso[tourId] =
        true;


    if (
        cantidades[tourId] === undefined
    ) {

        cantidades[tourId] = 1;

    }


    const datos =
        new URLSearchParams();


    datos.append(
        "csrf_token",
        obtenerCsrfToken()
    );


    datos.append(
        "cantidad",
        cantidades[tourId]
    );


    datos.append(
        "tipo_visita_id",
        tipoVisitaId
    );


    try {

        const respuesta =
            await fetch(
                `/recepcion/tours/${tourId}/ingreso`,
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
            );

            return;

        }


        document.getElementById(
            `total-${tourId}`
        ).textContent =
            resultado.total;
        
        actualizarEstadoCapacidad(
            tourId,
            resultado.total
        );


        cantidades[tourId] = 1;


        document.getElementById(
            `cantidad-${tourId}`
        ).textContent = 1;

    }

    catch (error) {

        console.error(error);

        alert(
            "No se pudo guardar el ingreso."
        );

    }

    finally {

        guardandoIngreso[tourId] =
            false;

    }

}


// ========================================
// CERRAR TOUR
// ========================================

function confirmarCierreTour(
    formulario
) {

    const circuito =
        formulario.dataset.circuito;


    const hora =
        formulario.dataset.hora;


    const tarjeta =
        formulario.closest(
            ".tour-card"
        );


    const total =
        tarjeta
            .querySelector(
                ".tour-total"
            )
            .textContent
            .trim();


    let mensaje =
        `¿Cerrar el tour de ${circuito}`;


    if (hora) {

        mensaje +=
            ` de las ${hora}`;

    }


    mensaje +=
        ` con ${total} personas?`;


    return confirm(
        mensaje
    );

}

// ========================================
// ACTUALIZAR ESTADO CAPACIDAD
// ========================================


function actualizarEstadoCapacidad(
    tourId,
    total
) {

    const elemento =
        document.getElementById(
            `total-${tourId}`
        );


    if (!elemento) {
        return;
    }


    const capacidad =
        parseInt(
            elemento.dataset.capacidad
        );


    if (
        isNaN(capacidad)
    ) {

        elemento.classList.remove(
            "tour-total-excedido"
        );

        return;
    }


    elemento.classList.toggle(
        "tour-total-excedido",
        Number(total) > capacidad
    );

}


// ========================================
// DESHACER ÚLTIMO INGRESO
// ========================================

async function deshacerIngreso(
    boton
) {

    const tourId =
        boton.dataset.tourId;


    if (
        !confirm(
            "¿Deshacer la última carga?"
        )
    ) {

        return;

    }


    const datos =
        new URLSearchParams();


    datos.append(
        "csrf_token",
        obtenerCsrfToken()
    );


    try {

        const respuesta =
            await fetch(
                `/recepcion/tours/${tourId}/deshacer`,
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
            );

            return;

        }


        document.getElementById(
            `total-${tourId}`
        ).textContent =
            resultado.total;
        
        actualizarEstadoCapacidad(
            tourId,
            resultado.total
        );


        alert(
            `Se eliminaron `
            +
            `${resultado.cantidad_eliminada} `
            +
            `de `
            +
            `${resultado.tipo_visita_eliminado}.`
        );

    }

    catch (error) {

        console.error(error);

        alert(
            "No se pudo deshacer la carga."
        );

    }

}