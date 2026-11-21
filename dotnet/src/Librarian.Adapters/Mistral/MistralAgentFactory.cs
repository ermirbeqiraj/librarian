using System.Reflection;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OpenAI;
using System.ClientModel;
using System.ClientModel.Primitives;

namespace Librarian.Adapters.Mistral;

internal static class MistralAgentFactory
{
    internal static AIAgent Create(IServiceProvider services, string apiKey, string baseUrl, string model, string reasoningEffort, int maxRounds)
    {
        var loggerFactory = services.GetRequiredService<ILoggerFactory>();

        var openAiClient = new OpenAIClient(new ApiKeyCredential(apiKey), new OpenAIClientOptions
        {
            Endpoint = new Uri(baseUrl),
            RetryPolicy = new ClientRetryPolicy(3),
            UserAgentApplicationId = "librarian",
            Transport = new HttpClientPipelineTransport(new HttpClient(new ThinkingShim())),
        });
        IChatClient chat = openAiClient.GetChatClient(model).AsIChatClient();

        var pipeline = chat.AsBuilder()
            .UseFunctionInvocation(loggerFactory, f => f.MaximumIterationsPerRequest = maxRounds)
            .Build(services);

        var agent = new ChatClientAgent(pipeline, new ChatClientAgentOptions
        {
            Name = "extractAgent",
            ChatOptions = new ChatOptions
            {
                Instructions = InstructionsText(),
                Reasoning = new ReasoningOptions
                {
                    Effort = reasoningEffort switch
                    {
                        "low" => ReasoningEffort.Low,
                        "medium" => ReasoningEffort.Medium,
                        "high" => ReasoningEffort.High,
                        _ => throw new InvalidOperationException($"Ingest:Extract:ReasoningEffort '{reasoningEffort}' is not one of low, medium, high."),
                    },
                },
            },
        }, loggerFactory, services);

        return new OpenTelemetryAgent(agent, "Microsoft.Agents.AI");
    }

    private static string InstructionsText()
    {
        var assembly = Assembly.GetExecutingAssembly();
        using var stream = assembly.GetManifestResourceStream("Librarian.Adapters.Mistral.Instructions.extract.md")
            ?? throw new InvalidOperationException("extract.md is not an embedded resource of Librarian.Adapters.");
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd().Trim();
    }
}
