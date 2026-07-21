async function login(){

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
        "http://127.0.0.1:5000/api/auth/login",
        {
            method:"POST",

            headers:{
                "Content-Type":
                "application/json"
            },

            body:JSON.stringify({
                email,
                password
            })
        }
    );

    const data =
    await response.json();

    if(data.token){

        localStorage.setItem(
            "token",
            data.token
        );

        localStorage.setItem(
            "username",
            data.username
        );

        window.location.href =
        "dashboard.html";
    }
    else{
        alert(data.message);
    }
}