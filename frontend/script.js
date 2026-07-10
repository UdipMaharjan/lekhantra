const API_BASE_URL = "https://YOUR-BACKEND-NAME.onrender.com";

let currentTextFile = null;

const pdfInput = document.getElementById("pdfInput");
const fileName = document.getElementById("fileName");
const uploadStatus = document.getElementById("uploadStatus");
const outputBox = document.getElementById("outputBox");

pdfInput.addEventListener("change", () => {
  if (pdfInput.files.length > 0) {
    fileName.textContent = pdfInput.files[0].name;
  } else {
    fileName.textContent = "No file selected";
  }
});

function setOutput(content) {
  outputBox.textContent = content;
}

function setLoading(message) {
  outputBox.classList.add("loading");
  outputBox.textContent = message;
}

function stopLoading() {
  outputBox.classList.remove("loading");
}

function formatOutput(data) {
  if (data.output) {
    return data.output;
  }

  if (data.answer) {
    return data.answer;
  }

  return JSON.stringify(data, null, 2);
}

function getErrorMessage(data) {
  if (data.detail && data.detail.message) {
    return data.detail.message;
  }

  if (data.message) {
    return data.message;
  }

  return "Something went wrong.";
}


async function uploadPDF() {
  const file = pdfInput.files[0];

  if (!file) {
    uploadStatus.textContent = "Please choose a PDF first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  uploadStatus.textContent = "Uploading and extracting text...";
  setLoading("Reading your PDF...");

  try {
    const response = await fetch(`${API_BASE_URL}/upload-pdf`, {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
    uploadStatus.textContent = getErrorMessage(data);
    setOutput(JSON.stringify(data, null, 2));
    return;
    }

    if (data.status === "success") {
      currentTextFile = data.text_file;

      uploadStatus.innerHTML = `
        <strong>Uploaded:</strong> ${data.filename}<br>
        <strong>Text file:</strong> ${data.text_file}<br>
        <strong>Characters:</strong> ${data.total_characters}
      `;

      setOutput(
        `PDF uploaded successfully.\n\nText preview:\n\n${data.text_preview}`
      );
    } else {
      uploadStatus.textContent = data.message || "Upload failed.";
      setOutput(JSON.stringify(data, null, 2));
    }
  } catch (error) {
    uploadStatus.textContent = "Could not connect to backend.";
    setOutput(`Error: ${error.message}`);
  } finally {
    stopLoading();
  }
}

async function generateViva() {
  if (!currentTextFile) {
    setOutput("Please upload a PDF first.");
    return;
  }

let count = Number(document.getElementById("questionCount").value) || 5;

if (count < 1 || count > 10) {
  setOutput("Please enter a number of questions between 1 and 10.");
  return;
}

  setLoading("Generating viva questions with Lekhantra...");

  try {
    const response = await fetch(`${API_BASE_URL}/ai-generate-viva`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text_file: currentTextFile,
        number_of_questions: count
      })
    });

    const data = await response.json();
    setOutput(formatOutput(data));
  } catch (error) {
    setOutput(`Error: ${error.message}`);
  } finally {
    stopLoading();
  }
}

async function generateExam() {
  if (!currentTextFile) {
    setOutput("Please upload a PDF first.");
    return;
  }

let count = Number(document.getElementById("questionCount").value) || 5;

if (count < 1 || count > 10) {
  setOutput("Please enter a number of questions between 1 and 10.");
  return;
}

  setLoading("Generating exam questions with Lekhantra...");

  try {
    const response = await fetch(`${API_BASE_URL}/ai-generate-exam`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text_file: currentTextFile,
        number_of_questions: count
      })
    });

    const data = await response.json();
    setOutput(formatOutput(data));
  } catch (error) {
    setOutput(`Error: ${error.message}`);
  } finally {
    stopLoading();
  }
}

async function askPDF() {
  if (!currentTextFile) {
    setOutput("Please upload a PDF first.");
    return;
  }

  const question = document.getElementById("pdfQuestion").value.trim();

  if (!question) {
    setOutput("Please type a question first.");
    return;
  }

  setLoading("Lekhantra is reading your notes...");

  try {
    const response = await fetch(`${API_BASE_URL}/ask-pdf`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text_file: currentTextFile,
        question: question
      })
    });

    const data = await response.json();
    setOutput(formatOutput(data));
  } catch (error) {
    setOutput(`Error: ${error.message}`);
  } finally {
    stopLoading();
  }
}

function clearOutput() {
  setOutput("Your generated answers will appear here.");
}

async function copyOutput() {
  const text = outputBox.textContent;

  if (!text || text === "Your generated answers will appear here.") {
    alert("There is nothing to copy yet.");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    alert("Copied to clipboard.");
  } catch (error) {
    alert("Could not copy text.");
  }
}

function downloadOutput() {
  const text = outputBox.textContent;

  if (!text || text === "Your generated answers will appear here.") {
    alert("There is nothing to download yet.");
    return;
  }

  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = "lekhantra-output.txt";
  link.click();

  URL.revokeObjectURL(url);
}