let cantidadGrupo = 1;

let tipoVisitaSeleccionado = null;

let circuitoSeleccionado = "";

let destinoSeleccionado = "";

let tourSeleccionado = null;


// ========================================
// CANTIDAD
// ========================================

function cambiarCantidadGrupo(cambio) {

    cantidadGrupo += cambio;


    if (cantidadGrupo < 1) {
        cantidadGrupo = 1;
    }


    document.getElementById(
        "grupo-cantidad"
    ).textContent = cantidadGrupo;


    document.getElementById(
        "grupo-cantidad-input"
    ).value = cantidadGrupo;

}


// ========================================
// TIPO DE VISITA
// ========================================

function seleccionarTipoVisita(boton) {

    tipoVisitaSeleccionado =
        boton.dataset.tipoId;

    circuitoSeleccionado =
        boton.dataset.circuito;


    document.getElementById(
        "grupo-tipo-input"
    ).value =
        tipoVisitaSeleccionado;


    // --------------------------------
    // MARCAR BOTÓN
    // --------------------------------

    document.querySelectorAll(
        "[data-tipo-id]"
    ).forEach(
        elemento => {

            elemento.classList.remove(
                "seleccionado"
            );

        }
    );


    boton.classList.add(
        "seleccionado"
    );


    // --------------------------------
    // REINICIAR DESTINO Y TOUR
    // --------------------------------

    destinoSeleccionado = "";

    tourSeleccionado = null;


    document.getElementById(
        "grupo-destino-input"
    ).value = "";


    document.getElementById(
        "grupo-tour-input"
    ).value = "";


    document.querySelectorAll(
        "[data-destino]"
    ).forEach(
        elemento => {

            elemento.classList.remove(
                "seleccionado"
            );

        }
    );


    document.querySelectorAll(
        ".grupo-tour"
    ).forEach(
        elemento => {

            elemento.classList.remove(
                "seleccionado"
            );

            elemento.hidden = true;

        }
    );


    // --------------------------------
    // MOSTRAR DESTINO
    // --------------------------------

    document.getElementById(
        "grupo-seccion-destino"
    ).hidden = false;


    document.getElementById(
        "grupo-seccion-tours"
    ).hidden = true;


    document.getElementById(
        "grupo-seccion-confirmar"
    ).hidden = true;


    // --------------------------------
    // AVISO SIN CIRCUITO
    // --------------------------------

    const aviso =
        document.getElementById(
            "grupo-sin-circuito"
        );


    aviso.hidden =
        circuitoSeleccionado !== "";

}


// ========================================
// DESTINO
// ========================================

function seleccionarDestino(boton) {

    destinoSeleccionado =
        boton.dataset.destino;


    document.getElementById(
        "grupo-destino-input"
    ).value =
        destinoSeleccionado;


    document.querySelectorAll(
        "[data-destino]"
    ).forEach(
        elemento => {

            elemento.classList.remove(
                "seleccionado"
            );

        }
    );


    boton.classList.add(
        "seleccionado"
    );


    // --------------------------------
    // PRIVADA
    // --------------------------------

    if (
        destinoSeleccionado ===
        "PRIVADA"
    ) {

        tourSeleccionado = null;


        document.getElementById(
            "grupo-tour-input"
        ).value = "";


        document.getElementById(
            "grupo-seccion-tours"
        ).hidden = true;


        document.getElementById(
            "grupo-seccion-confirmar"
        ).hidden = false;


        return;

    }


    // --------------------------------
    // NORMAL
    // --------------------------------

    document.getElementById(
        "grupo-seccion-confirmar"
    ).hidden = true;


    mostrarToursCompatibles();

}


// ========================================
// MOSTRAR TOURS COMPATIBLES
// ========================================

function mostrarToursCompatibles() {

    const seccionTours =
        document.getElementById(
            "grupo-seccion-tours"
        );


    const mensajeSinTours =
        document.getElementById(
            "grupo-sin-tours"
        );


    seccionTours.hidden = false;


    let cantidadTours = 0;


    document.querySelectorAll(
        ".grupo-tour"
    ).forEach(
        tour => {

            const circuitoTour =
                tour.dataset.circuito;


            const compatible =
                circuitoTour ===
                circuitoSeleccionado;


            tour.hidden = !compatible;


            tour.classList.remove(
                "seleccionado"
            );


            if (compatible) {
                cantidadTours++;
            }

        }
    );


    mensajeSinTours.hidden =
        cantidadTours > 0;


    tourSeleccionado = null;


    document.getElementById(
        "grupo-tour-input"
    ).value = "";

}


// ========================================
// SELECCIONAR TOUR
// ========================================

function seleccionarTour(boton) {

    tourSeleccionado =
        boton.dataset.tourId;


    document.getElementById(
        "grupo-tour-input"
    ).value =
        tourSeleccionado;


    document.querySelectorAll(
        ".grupo-tour"
    ).forEach(
        elemento => {

            elemento.classList.remove(
                "seleccionado"
            );

        }
    );


    boton.classList.add(
        "seleccionado"
    );


    document.getElementById(
        "grupo-seccion-confirmar"
    ).hidden = false;

}


// ========================================
// VALIDAR ANTES DE ENVIAR
// ========================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const formulario =
            document.getElementById(
                "form-grupo"
            );


        formulario.addEventListener(
            "submit",
            function (evento) {


                if (
                    !tipoVisitaSeleccionado
                ) {

                    evento.preventDefault();

                    alert(
                        "Seleccioná un tipo de visita."
                    );

                    return;

                }


                if (
                    !destinoSeleccionado
                ) {

                    evento.preventDefault();

                    alert(
                        "Seleccioná cómo ingresa el grupo."
                    );

                    return;

                }


                if (
                    destinoSeleccionado ===
                    "NORMAL"
                    &&
                    circuitoSeleccionado ===
                    ""
                ) {

                    evento.preventDefault();

                    alert(
                        "Este tipo de visita no tiene un circuito de recepción configurado."
                    );

                    return;

                }


                if (
                    destinoSeleccionado ===
                    "NORMAL"
                    &&
                    !tourSeleccionado
                ) {

                    evento.preventDefault();

                    alert(
                        "Seleccioná un tour."
                    );

                    return;

                }


                let mensaje =
                    `Registrar grupo de ${cantidadGrupo} personas?`;


                if (
                    destinoSeleccionado ===
                    "PRIVADA"
                ) {

                    mensaje =
                        `¿Registrar grupo privado de ${cantidadGrupo} personas?`;

                }


                if (
                    !confirm(mensaje)
                ) {

                    evento.preventDefault();

                }

            }
        );

    }
);