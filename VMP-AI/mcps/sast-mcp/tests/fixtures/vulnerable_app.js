// Test fixture: JavaScript file with intentional vulnerability for AST context testing
const express = require('express');
const app = express();

function handleUserInput(req, res) {
    // Intentional vulnerability: eval of user input
    const result = eval(req.query.code);
    res.send(result);
}

const processData = (data) => {
    return JSON.parse(data);
};

app.get('/run', handleUserInput);
app.listen(3000);
