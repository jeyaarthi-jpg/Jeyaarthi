const token = localStorage.getItem("token");

async function uploadPDF() {

    const file =
    document.getElementById("pdfFile").files[0];

    if (!file) {
        alert("Please select a PDF file");
        return;
    }

    const formData = new FormData();

    formData.append(
        "file",
        file
    );

    try {

        const uploadResponse =
        await fetch(
            "http://127.0.0.1:5000/api/expense/upload",
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`
                },
                body: formData
            }
        );

        const result =
        await uploadResponse.json();

        console.log(result);

        if (!uploadResponse.ok) {

            alert(
                result.message ||
                "Upload failed"
            );

            return;
        }

        alert(
            "PDF uploaded successfully"
        );

        loadAnalysis();

    } catch(error) {

        console.error(error);

        alert(
            "Error uploading PDF"
        );
    }
}

async function loadAnalysis() {

    try {

        const response =
        await fetch(
            "http://127.0.0.1:5000/api/expense/analysis",
            {
                headers: {
                    Authorization:
                    `Bearer ${token}`
                }
            }
        );

        const data =
        await response.json();

        console.log(data);

        const labels =
        Object.keys(
            data.category_breakdown || {}
        );

        const values =
        Object.values(
            data.category_breakdown || {}
        );

        document.getElementById(
            "result"
        ).innerHTML =

        `<h3>Total Expense:
        ₹${data.total_expense || 0}</h3>`;

        if(labels.length > 0){

            new Chart(
                document.getElementById(
                    "expenseChart"
                ),
                {
                    type:"pie",
                    data:{
                        labels:labels,
                        datasets:[
                            {
                                data:values
                            }
                        ]
                    }
                }
            );
        }

    } catch(error){

        console.error(error);
    }
}

function logout(){

    localStorage.clear();

    window.location.href =
    "login.html";
}

loadAnalysis();