document.addEventListener("DOMContentLoaded", function () {

    const pantallaResultado = document.getElementById(
        "resultado-calculadora"
    );

    const pantallaOperacion = document.getElementById(
        "operacion-calculadora"
    );

    const botonesNumeros = document.querySelectorAll(
        "[data-numero]"
    );

    const botonesOperadores = document.querySelectorAll(
        "[data-operador]"
    );

    let valorActual = "0";
    let valorAnterior = null;
    let operadorActual = null;
    let esperandoNuevoNumero = false;
    let resultadoMostrado = false;


    function formatearNumero(valor) {

        const numero = Number(valor);

        if (!Number.isFinite(numero)) {
            return "Error";
        }

        return new Intl.NumberFormat(
            "es-AR",
            {
                maximumFractionDigits: 10
            }
        ).format(numero);

    }


    function simboloOperador(operador) {

        const simbolos = {
            "+": "+",
            "-": "−",
            "*": "×",
            "/": "÷"
        };

        return simbolos[operador] || operador;

    }


    function actualizarPantalla() {

        if (valorActual === "Error") {
            pantallaResultado.textContent = "Error";
            return;
        }

        pantallaResultado.textContent = formatearNumero(
            valorActual
        );

        if (
            valorAnterior !== null
            && operadorActual !== null
        ) {
            pantallaOperacion.textContent =
                `${formatearNumero(valorAnterior)} ` +
                `${simboloOperador(operadorActual)}`;
        } else {
            pantallaOperacion.textContent = "";
        }

    }


    function ingresarNumero(numero) {

        if (
            esperandoNuevoNumero
            || resultadoMostrado
            || valorActual === "Error"
        ) {
            valorActual = numero;
            esperandoNuevoNumero = false;
            resultadoMostrado = false;
        } else if (valorActual === "0") {
            valorActual = numero;
        } else if (valorActual.length < 16) {
            valorActual += numero;
        }

        actualizarPantalla();

    }


    function ingresarDecimal() {

        if (
            esperandoNuevoNumero
            || resultadoMostrado
            || valorActual === "Error"
        ) {
            valorActual = "0.";
            esperandoNuevoNumero = false;
            resultadoMostrado = false;
        } else if (!valorActual.includes(".")) {
            valorActual += ".";
        }

        actualizarPantalla();

    }


    function calcular(
        primerValor,
        segundoValor,
        operador
    ) {

        const primero = Number(primerValor);
        const segundo = Number(segundoValor);

        switch (operador) {

            case "+":
                return primero + segundo;

            case "-":
                return primero - segundo;

            case "*":
                return primero * segundo;

            case "/":

                if (segundo === 0) {
                    return null;
                }

                return primero / segundo;

            default:
                return segundo;

        }

    }


    function seleccionarOperador(nuevoOperador) {

        if (valorActual === "Error") {
            limpiarCalculadora();
            return;
        }

        if (
            operadorActual !== null
            && !esperandoNuevoNumero
        ) {
            obtenerResultado();
        }

        valorAnterior = valorActual;
        operadorActual = nuevoOperador;
        esperandoNuevoNumero = true;
        resultadoMostrado = false;

        actualizarPantalla();

    }


    function obtenerResultado() {

        if (
            operadorActual === null
            || valorAnterior === null
            || esperandoNuevoNumero
        ) {
            return;
        }

        const primerValor = valorAnterior;
        const segundoValor = valorActual;
        const operadorUsado = operadorActual;

        const resultado = calcular(
            primerValor,
            segundoValor,
            operadorUsado
        );

        pantallaOperacion.textContent =
            `${formatearNumero(primerValor)} ` +
            `${simboloOperador(operadorUsado)} ` +
            `${formatearNumero(segundoValor)} =`;

        if (resultado === null) {
            valorActual = "Error";
        } else {
            valorActual = String(
                Number(resultado.toFixed(10))
            );
        }

        valorAnterior = null;
        operadorActual = null;
        esperandoNuevoNumero = false;
        resultadoMostrado = true;

        pantallaResultado.textContent =
            valorActual === "Error"
                ? "Error"
                : formatearNumero(valorActual);

    }


    function limpiarCalculadora() {

        valorActual = "0";
        valorAnterior = null;
        operadorActual = null;
        esperandoNuevoNumero = false;
        resultadoMostrado = false;

        actualizarPantalla();

    }


    function borrarUltimo() {

        if (
            esperandoNuevoNumero
            || resultadoMostrado
            || valorActual === "Error"
        ) {
            valorActual = "0";
            resultadoMostrado = false;
        } else if (valorActual.length > 1) {
            valorActual = valorActual.slice(0, -1);
        } else {
            valorActual = "0";
        }

        actualizarPantalla();

    }


    function calcularPorcentaje() {

        if (valorActual === "Error") {
            return;
        }

        valorActual = String(
            Number(valorActual) / 100
        );

        actualizarPantalla();

    }


    botonesNumeros.forEach(function (boton) {

        boton.addEventListener("click", function () {

            ingresarNumero(
                boton.dataset.numero
            );

        });

    });


    botonesOperadores.forEach(function (boton) {

        boton.addEventListener("click", function () {

            seleccionarOperador(
                boton.dataset.operador
            );

        });

    });


    document.querySelector(
        '[data-accion="decimal"]'
    ).addEventListener(
        "click",
        ingresarDecimal
    );


    document.querySelector(
        '[data-accion="resultado"]'
    ).addEventListener(
        "click",
        obtenerResultado
    );


    document.querySelector(
        '[data-accion="limpiar"]'
    ).addEventListener(
        "click",
        limpiarCalculadora
    );


    document.querySelector(
        '[data-accion="borrar"]'
    ).addEventListener(
        "click",
        borrarUltimo
    );


    document.querySelector(
        '[data-accion="porcentaje"]'
    ).addEventListener(
        "click",
        calcularPorcentaje
    );


    document.addEventListener("keydown", function (evento) {

        const tecla = evento.key;

        if (/^[0-9]$/.test(tecla)) {
            ingresarNumero(tecla);
            return;
        }

        if (tecla === "." || tecla === ",") {
            evento.preventDefault();
            ingresarDecimal();
            return;
        }

        if (["+", "-", "*", "/"].includes(tecla)) {
            evento.preventDefault();
            seleccionarOperador(tecla);
            return;
        }

        if (tecla === "Enter" || tecla === "=") {
            evento.preventDefault();
            obtenerResultado();
            return;
        }

        if (tecla === "Backspace") {
            borrarUltimo();
            return;
        }

        if (tecla === "Escape") {
            limpiarCalculadora();
            return;
        }

        if (tecla === "%") {
            calcularPorcentaje();
        }

    });


    actualizarPantalla();

});