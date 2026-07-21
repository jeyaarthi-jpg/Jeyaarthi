async function register(){

    const username =
    document.getElementById(
        "username"
    ).value;

    const email =
    document.getElementById(
        "email"
    ).value;

    const password =
    document.getElementById(
        "password"
    ).value;

    const response =
    await fetch(
        "http://127.0.0.1:5000/api/auth/register",
        {
            method:"POST",

            headers:{
                "Content-Type":
                "application/json"
            },

            body:JSON.stringify({
                username,
                email,
                password
            })
        }
    );

    const data =
    await response.json();

    alert(data.message);

    window.location.href =
    "login.html";
}