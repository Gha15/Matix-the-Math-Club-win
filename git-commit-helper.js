const { execSync } = require('child_process');
const readline = require('readline');

// 1. Stage all project files immediately
console.log('Staging files...');
try {
    execSync('git add .', { stdio: 'inherit' });
} catch (e) {
    // Continue even if staging has minor warnings
}

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

let timerActive = true;
let secondsLeft = 5;

console.log('Enter your commit message (Auto-fallback to "fixed a thing" if no input in 5s):');
process.stdout.write(`(${secondsLeft}s) > `);

// 2. Start a background countdown checker
const countdown = setInterval(() => {
    // If the user started typing anything, rl.line won't be empty
    if (rl.line.length > 0 && timerActive) {
        timerActive = false;
        clearInterval(countdown);
        // Clear the countdown prefix line to let the user type cleanly
        readline.clearLine(process.stdout, 0);
        readline.cursorTo(process.stdout, 0);
        process.stdout.write(`> ${rl.line}`);
        return;
    }

    secondsLeft--;

    if (secondsLeft <= 0) {
        clearInterval(countdown);
        if (timerActive) {
            console.log('\n\n[Timeout] No interaction detected for 5 seconds.');
            executeGitCommit('fixed a thing');
        }
    } else if (timerActive) {
        // Update the visible timer countdown prefix dynamically without disrupting input
        const currentPos = rl.cursor;
        readline.clearLine(process.stdout, 0);
        readline.cursorTo(process.stdout, 0);
        process.stdout.write(`(${secondsLeft}s) > ${rl.line}`);
        readline.cursorTo(process.stdout, currentPos + `(${secondsLeft}s) > `.length);
    }
}, 1000);

// 3. Wait for the user to press Enter normally
rl.on('line', (userInput) => {
    if (timerActive) {
        timerActive = false;
        clearInterval(countdown);
    }
    
    const finalMessage = userInput.trim() ? userInput.trim() : 'fixed a thing';
    executeGitCommit(finalMessage);
});

// 4. Run final deployment tasks
function executeGitCommit(msg) {
    rl.close();
    try {
        console.log(`\nCommitting with message: "${msg}"`);
        execSync(`git commit -m "${msg}"`, { stdio: 'inherit' });
        
        console.log('Pushing updates to remote master branch...');
        execSync('git push origin master', { stdio: 'inherit' });
        
        console.log('\nDeployment finished successfully!');
        process.exit(0);
    } catch (error) {
        console.error('\nGit deployment failed. Verify you have local file changes.');
        process.exit(1);
    }
}
