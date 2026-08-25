const { execSync } = require('child_process');
const readline = require('readline');

// Set up interface to read terminal input
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

let messageSubmitted = false;

// 1. Automatically stage all current project modifications
console.log('Staging files...');
execSync('git add .', { stdio: 'inherit' });

// 2. Start the 5-second countdown timer for the fallback option
const timer = setTimeout(() => {
    if (!messageSubmitted) {
        console.log('\n\n[Timeout] No input detected for 5 seconds.');
        processCommit('fixed a thing');
    }
}, 5000);

// 3. Prompt the developer for a custom commit message
rl.question('Enter your commit message (Auto-fallback in 5s): ', (userInput) => {
    messageSubmitted = true;
    clearTimeout(timer); // Cancel the automatic fallback timer
    
    // Use fallback message if user just hits enter without typing
    const finalMessage = userInput.trim() ? userInput.trim() : 'fixed a thing';
    processCommit(finalMessage);
});

// 4. Execute the final terminal commands
function processCommit(msg) {
    rl.close();
    try {
        console.log(`\nCommitting with message: "${msg}"`);
        execSync(`git commit -m "${msg}"`, { stdio: 'inherit' });
        
        console.log('Pushing updates to remote branch...');
        execSync('git push origin master', { stdio: 'inherit' });
        
        console.log('\nDeployment completely finished successfully!');
    } catch (error) {
        console.error('\nGit deployment failed. Ensure you have changes to commit.');
        process.exit(1);
    }
}
